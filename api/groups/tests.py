import json
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from activity.models import Event, Kind as EventKind
from home.tests import make_ride, log_in_to_admin
from home.tests import make_user as make_account
from notifications.models import Kind, Notification
from rides.models import Ride, RideRequest
from . import services
from .models import Group, Membership


def make_user(first, last="Mäkinen", **fields):
    # Someone using the app now: logged in recently, so able to act as admin
    fields.setdefault("last_login", timezone.now())
    return make_account(first, last, **fields)


def add_member(group, user, joined_days_ago=0, admin=False):
    return Membership.objects.create(
        group=group, user=user, status=Membership.Status.ACTIVE,
        role=Membership.Role.ADMIN if admin else Membership.Role.MEMBER,
        joined_at=timezone.now() - timedelta(days=joined_days_ago),
    )


def role(group, user):
    membership = Membership.objects.filter(group=group, user=user).first()
    return membership and (membership.role if membership.status == Membership.Status.ACTIVE else membership.status)


def notified(user, kind):
    return Notification.objects.filter(recipient=user, kind=kind).exists()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class GroupTestCase(TestCase):
    def setUp(self):
        self.admin = make_user("Aino")
        self.group = services.create_group(self.admin, "Skinnarila commuters")
        self.url = reverse("group_detail", args=[self.group.pk])

    def post(self, user, action, **data):
        self.client.force_login(user)
        # Notifications are delivered (emailed) once the change is saved
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url, {"action": action, **data})


class MakingAndJoiningTests(GroupTestCase):
    def test_the_maker_is_admin(self):
        self.assertEqual(role(self.group, self.admin), Membership.Role.ADMIN)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("groups")), "Skinnarila commuters")

    def test_making_a_group_from_the_page(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("groups"), {"name": "  LAB   Lahti ", "description": "Lahti staff"})
        group = Group.objects.get(name="LAB Lahti")
        self.assertRedirects(response, reverse("group_detail", args=[group.pk]))
        # Names are unique, whatever their case
        response = self.client.post(reverse("groups"), {"name": "lab lahti"})
        self.assertContains(response, "There is already a group called lab lahti")

    def test_asking_to_join_and_being_accepted(self):
        jamie = make_user("Jamie")
        self.post(jamie, "join")
        self.assertEqual(role(self.group, jamie), Membership.Status.PENDING)
        self.assertTrue(notified(self.admin, Kind.GROUP_JOIN_REQUESTED))

        request = Membership.objects.get(user=jamie)
        self.post(self.admin, "accept", membership=request.pk)
        self.assertEqual(role(self.group, jamie), Membership.Role.MEMBER)
        self.assertTrue(notified(jamie, Kind.GROUP_JOIN_ACCEPTED))
        self.assertIn("accepted you into the group Skinnarila commuters", mail.outbox[-1].body)

    def test_declined_requests_can_be_made_again(self):
        jamie = make_user("Jamie")
        self.post(jamie, "join")
        self.post(self.admin, "decline", membership=Membership.objects.get(user=jamie).pk)
        self.assertIsNone(role(self.group, jamie))
        self.assertTrue(notified(jamie, Kind.GROUP_JOIN_DECLINED))
        self.post(jamie, "join")
        self.assertEqual(role(self.group, jamie), Membership.Status.PENDING)

    def test_only_admins_manage_the_group(self):
        jamie, kalle = make_user("Jamie"), make_user("Kalle")
        add_member(self.group, jamie)
        self.post(kalle, "join")
        request = Membership.objects.get(user=kalle)
        for action in ("accept", "make_admin", "remove", "delete"):
            self.assertEqual(self.post(jamie, action, membership=request.pk).status_code, 403, action)
        self.assertEqual(role(self.group, kalle), Membership.Status.PENDING)


class RideVisibilityTests(GroupTestCase):
    def setUp(self):
        super().setUp()
        self.member, self.outsider = make_user("Jamie"), make_user("Kalle")
        add_member(self.group, self.member)
        self.ride = make_ride(self.admin, groups_only=True, max_passengers=3)
        self.ride.groups.add(self.group)
        self.public = make_ride(self.admin)

    def searched(self, user):
        self.client.force_login(user)
        return {ride.pk for ride in self.client.post(reverse("search"), {}).context["page"]}

    def test_only_members_find_group_rides(self):
        self.assertEqual(self.searched(self.member), {self.ride.pk, self.public.pk})
        self.assertEqual(self.searched(self.outsider), {self.public.pk})
        self.client.force_login(self.outsider)
        self.assertNotContains(self.client.get(reverse("home")), reverse("ride_detail", args=[self.ride.pk]))

    def test_outsiders_opening_a_shared_link_are_told_which_group_to_join(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("ride_detail", args=[self.ride.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, self.url, status_code=403)
        self.assertNotContains(response, "Lappeenranta", status_code=403)
        # Nor can they ask to join it
        self.assertEqual(self.client.post(reverse("request_ride", args=[self.ride.pk])).status_code, 404)

    def test_passengers_keep_their_ride_after_leaving_the_group(self):
        RideRequest.objects.create(ride=self.ride, passenger=self.member, status=RideRequest.Status.ACCEPTED)
        self.post(self.member, "leave")
        self.assertIn(self.ride.pk, self.searched(self.member))

    @patch("home.views.build_route", return_value=None)
    def test_posting_to_groups(self, _route):
        place = lambda name: json.dumps({"displayName": name, "location": {"lat": 61.0, "lng": 28.2}})
        data = {"offer": "on", "max_passengers": "3", "start_json": place("Lappeenranta"), "destination_json": place("Lahti"),
                "one_time": "oneTime", "one_way": "oneWay", "leaving_at_date_time": "2099-10-14T07:30"}
        self.client.force_login(self.member)
        # A group must be chosen, and only the driver's own
        other = services.create_group(self.outsider, "Not mine")
        self.assertContains(self.client.post(reverse("add"), {**data, "audience": "groups"}), "Choose at least one of your groups")
        self.assertEqual(self.client.post(reverse("add"), {**data, "audience": "groups", "groups": [other.pk]}).status_code, 200)
        self.client.post(reverse("add"), {**data, "audience": "groups", "groups": [self.group.pk]})
        ride = Ride.objects.get(driver=self.member)
        self.assertTrue(ride.groups_only)
        self.assertEqual(list(ride.groups.all()), [self.group])
        self.assertEqual(Event.objects.get(kind=EventKind.RIDE_POSTED).data["groups"], 1)


class AdminTests(GroupTestCase):
    def setUp(self):
        super().setUp()
        self.jamie, self.kalle = make_user("Jamie"), make_user("Kalle")
        self.jamie_membership = add_member(self.group, self.jamie, joined_days_ago=30)
        self.kalle_membership = add_member(self.group, self.kalle, joined_days_ago=10)

    def test_making_admins_and_handing_over(self):
        self.post(self.admin, "make_admin", membership=self.kalle_membership.pk)
        self.assertEqual(role(self.group, self.kalle), Membership.Role.ADMIN)
        self.assertTrue(notified(self.kalle, Kind.GROUP_ADMIN_GRANTED))

        self.post(self.admin, "hand_over", membership=self.jamie_membership.pk)
        self.assertEqual(role(self.group, self.jamie), Membership.Role.ADMIN)
        self.assertEqual(role(self.group, self.admin), Membership.Role.MEMBER)

    def test_the_only_admin_cannot_just_step_down(self):
        response = self.post(self.admin, "step_down")
        self.assertEqual(role(self.group, self.admin), Membership.Role.ADMIN)
        self.assertContains(self.client.get(response.url), "You are the only admin")

        self.post(self.admin, "make_admin", membership=self.kalle_membership.pk)
        self.post(self.admin, "step_down")
        self.assertEqual(role(self.group, self.admin), Membership.Role.MEMBER)

    def test_admins_cannot_remove_each_other(self):
        self.post(self.admin, "make_admin", membership=self.kalle_membership.pk)
        self.post(self.kalle, "remove", membership=Membership.objects.get(user=self.admin).pk)
        self.assertEqual(role(self.group, self.admin), Membership.Role.ADMIN)

    def test_removed_drivers_rides_are_hidden_not_made_public(self):
        ride = make_ride(self.jamie, groups_only=True)
        ride.groups.add(self.group)
        self.post(self.admin, "remove", membership=self.jamie_membership.pk)
        self.assertIsNone(role(self.group, self.jamie))
        self.assertTrue(notified(self.jamie, Kind.GROUP_REMOVED))
        ride.refresh_from_db()
        self.assertTrue(ride.is_hidden())
        self.assertFalse(Ride.objects.visible_to(self.kalle).filter(pk=ride.pk).exists())
        self.assertTrue(notified(self.jamie, Kind.RIDE_HIDDEN))
        # Its driver is shown why, and how to fix it
        self.client.force_login(self.jamie)
        self.assertContains(self.client.get(reverse("ride_detail", args=[ride.pk])), "Nobody can find this ride")

    def test_deleting_a_group(self):
        ride = make_ride(self.kalle, groups_only=True)
        ride.groups.add(self.group)
        self.post(self.admin, "delete")
        self.assertFalse(Group.objects.exists())
        self.assertTrue(notified(self.jamie, Kind.GROUP_DELETED))
        self.assertFalse(Ride.objects.visible_to(self.jamie).filter(pk=ride.pk).exists())
        self.assertTrue(notified(self.kalle, Kind.RIDE_HIDDEN))
        # The notification keeps the group's name but leads nowhere
        notification = Notification.objects.get(recipient=self.jamie, kind=Kind.GROUP_DELETED)
        self.assertIn("Skinnarila commuters", notification.message())
        self.assertIsNone(notification.url())


@override_settings(GROUP_ADMIN_AWAY_DAYS=180)
class AdminLockoutTests(GroupTestCase):
    """A group always gets an admin who can act (services.ensure_admin)."""

    def setUp(self):
        super().setUp()
        self.jamie, self.kalle = make_user("Jamie"), make_user("Kalle")
        # Jamie has been a member longer, so is the one to take over
        add_member(self.group, self.jamie, joined_days_ago=30)
        add_member(self.group, self.kalle, joined_days_ago=10)

    def assert_took_over(self, user):
        self.assertEqual(role(self.group, user), Membership.Role.ADMIN)
        self.assertEqual(role(self.group, self.kalle), Membership.Role.MEMBER)
        self.assertTrue(notified(user, Kind.GROUP_ADMIN_HANDED_OVER))
        # An essential email: it goes even to those who only want those
        self.assertTrue(any("You are now an admin of the group" in m.body for m in mail.outbox if m.to == [user.email]))

    def test_the_only_admin_deleting_their_account(self):
        self.client.force_login(self.admin)
        page = self.client.get(reverse("account"))
        self.assertContains(page, "You are the only admin of these groups")
        self.assertContains(page, "Jamie M. will become its admin")

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("account"), {"form": "delete", "delete-password": "Passw0rd!x"})
        self.assertFalse(User.objects.filter(pk=self.admin.pk).exists())
        self.assert_took_over(self.jamie)

    def test_the_last_member_deleting_their_account_deletes_the_group(self):
        Membership.objects.exclude(user=self.admin).delete()
        waiting = make_user("Liisa")
        self.post(waiting, "join")
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("account")), "you are its last member, so it will be deleted")
        self.client.post(reverse("account"), {"form": "delete", "delete-password": "Passw0rd!x"})
        self.assertFalse(Group.objects.exists())
        self.assertTrue(notified(waiting, Kind.GROUP_CLOSED))

    def test_a_blocked_admin(self):
        # e.g. a staff admin blocking the account of someone who left LUT/LAB
        self.admin.is_active = False
        with self.captureOnCommitCallbacks(execute=True):
            self.admin.save()
        self.assert_took_over(self.jamie)
        # They stay a member, and keep their role in case they come back
        self.assertEqual(role(self.group, self.admin), Membership.Role.ADMIN)

    def test_an_admin_whose_email_address_is_no_longer_confirmed(self):
        # The yearly check that members still work at LUT/LAB
        self.admin.email_confirmed_at = None
        with self.captureOnCommitCallbacks(execute=True):
            self.admin.save()
        self.assert_took_over(self.jamie)

    def test_members_who_cannot_act_are_passed_over(self):
        User.objects.filter(pk=self.jamie.pk).update(is_active=False)
        self.admin.is_active = False
        self.admin.save()
        self.assertEqual(role(self.group, self.kalle), Membership.Role.ADMIN)
        self.assertEqual(role(self.group, self.jamie), Membership.Role.MEMBER)

    def test_an_admin_away_for_long_gets_help_when_someone_asks_to_join(self):
        long_ago = timezone.now() - timedelta(days=200)
        User.objects.filter(pk=self.admin.pk).update(last_login=long_ago)
        liisa = make_user("Liisa")
        self.post(liisa, "join")
        self.assert_took_over(self.jamie)
        # The new admin is the one asked
        self.assertTrue(notified(self.jamie, Kind.GROUP_JOIN_REQUESTED))
        self.assertFalse(notified(self.admin, Kind.GROUP_JOIN_REQUESTED))

    def test_using_the_app_counts_though_the_session_is_old(self):
        long_ago = timezone.now() - timedelta(days=200)
        User.objects.filter(pk=self.admin.pk).update(last_login=long_ago)
        Event.objects.create(user=self.admin, kind=EventKind.ACTIVE, created_at=timezone.now() - timedelta(days=2))
        self.post(make_user("Liisa"), "join")
        self.assertEqual(role(self.group, self.jamie), Membership.Role.MEMBER)
        self.assertTrue(notified(self.admin, Kind.GROUP_JOIN_REQUESTED))

    def test_the_first_member_to_come_back_takes_over(self):
        long_ago = timezone.now() - timedelta(days=200)
        User.objects.update(last_login=long_ago)
        # Nobody can act: the group waits
        services.ensure_admin(self.group)
        self.assertEqual(role(self.group, self.kalle), Membership.Role.MEMBER)
        # Kalle's first visit of the day
        self.client.force_login(self.kalle)
        self.client.get(reverse("home"))
        self.assertEqual(role(self.group, self.kalle), Membership.Role.ADMIN)

    def test_the_only_admin_leaving_chooses_who_takes_over(self):
        self.client.force_login(self.admin)
        page = self.client.get(self.url)
        self.assertContains(page, "You are the only admin. Who should take over?")
        self.post(self.admin, "leave", successor=Membership.objects.get(user=self.kalle).pk)
        self.assertIsNone(role(self.group, self.admin))
        self.assertEqual(role(self.group, self.kalle), Membership.Role.ADMIN)
        self.assertEqual(role(self.group, self.jamie), Membership.Role.MEMBER)

    def test_the_only_admin_leaving_without_choosing(self):
        self.post(self.admin, "leave")
        self.assert_took_over(self.jamie)

    def test_the_last_member_leaving_deletes_the_group(self):
        Membership.objects.exclude(user=self.admin).delete()
        response = self.post(self.admin, "leave")
        self.assertRedirects(response, reverse("groups"))
        self.assertFalse(Group.objects.exists())

    def test_staff_can_see_groups_nobody_can_answer_for(self):
        User.objects.update(is_active=False)
        staff = make_user("Ada", is_staff=True, is_superuser=True)
        log_in_to_admin(self.client, staff)
        page = self.client.get(reverse("admin:groups_group_changelist"), {"needs_admin": "yes"})
        self.assertContains(page, "Skinnarila commuters")


class HomePageTests(GroupTestCase):
    """The home page's groups section (home.views.group_summary)."""

    def setUp(self):
        super().setUp()
        self.member = make_user("Jamie")
        add_member(self.group, self.member)
        self.client.force_login(self.member)

    def group_ride(self, driver, days_old=0):
        ride = make_ride(driver, groups_only=True)
        ride.groups.add(self.group)
        Ride.objects.filter(pk=ride.pk).update(created_at=timezone.now() - timedelta(days=days_old))
        return ride

    def test_members_see_their_groups_and_rides_new_since_their_last_visit(self):
        Event.objects.create(user=self.member, kind=EventKind.ACTIVE, created_at=timezone.now() - timedelta(days=3))
        old, new = self.group_ride(self.admin, days_old=5), self.group_ride(self.admin)
        own = self.group_ride(self.member)
        response = self.client.get(reverse("home"))

        self.assertContains(response, "Your groups")
        self.assertContains(response, self.url)
        rides = {ride.pk: ride.is_new for ride in response.context["group_rides"]}
        # The user's own rides are not listed: they are under "Your upcoming rides"
        self.assertEqual(rides, {old.pk: False, new.pk: True})
        self.assertNotIn(own.pk, rides)
        self.assertEqual(response.context["group_memberships"][0].new_rides, 1)
        self.assertContains(response, "1 new ride")
        # Group rides are not shown again under the recently posted rides
        self.assertNotIn(new.pk, {ride.pk for ride in response.context["recent_rides"]})

    def test_admins_see_requests_waiting(self):
        self.post(make_user("Kalle"), "join")
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("home")), "1 to answer")

    def test_without_groups_an_invitation_to_join_one(self):
        self.client.force_login(make_user("Kalle"))
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Ride with people you know")
        self.assertNotContains(response, "Your groups")

    def test_offering_a_ride_to_groups_from_the_home_page(self):
        page = self.client.get(reverse("add"), {"audience": "groups"}).content.decode()
        self.assertRegex(page, r'value="groups"[^>]*checked')
