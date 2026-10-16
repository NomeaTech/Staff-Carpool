// Runs fn once the page's elements are there: at once on pages shown by
// Turbo (static/js/turbo-setup.js), after the page is parsed on others.
// For page scripts, instead of window "load" or "DOMContentLoaded", which
// only come for the first page.
function onPageReady(fn) {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", fn, { once: true });
    } else {
        fn();
    }
}

// initial_place: a place (as in via_json) to start with, e.g. when editing a ride
function viaAdd(initial_place = null) {
    count = document.getElementById("div-via").children.length;
    if (count > 7) {
        return
    }

    inputDiv = document.getElementById("div-via");
    inputDiv.removeAttribute("hidden", "");

    id = Date.now().toString(36) + Math.floor(Math.pow(10, 12) + Math.random() * 9*Math.pow(10, 12)).toString(36)
    inputDiv.insertAdjacentHTML(
        'beforeend', 
        `<div class="grid grid-cols-5 col-span-5 gap-4 div-via-input w-full" id="${id}-div">
            <div id="div-autocomplete-via-${id}" class="col-span-4 skeleton rounded-field h-12 w-full"></div>
            <button id="${id}-button" data-idref="${id}" class="btn btn-error col-span-1" onclick="viaRemove(this)" type="button">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" fill="currentColor" stroke="currentColor" class="scale-120"><!--!Font Awesome Free v7.3.1 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M96 320C96 302.3 110.3 288 128 288L512 288C529.7 288 544 302.3 544 320C544 337.7 529.7 352 512 352L128 352C110.3 352 96 337.7 96 320z"/></svg>
            </button>
        </div>`
    );

    autocomplete_init(`div-autocomplete-via-${id}`, `via_${id}`, "Via", null, false,
        initial_place && typeof initial_place === "object" ? initial_place : null);

    if (count >= 7) {
        document.getElementById("add_via").disabled = true;
    }
}

function viaRemove(element) {
    div = document.getElementById(`${element.dataset.idref}-div`);
    div.remove()

    vias = document.getElementsByClassName("div-via-input");
    if (vias.length == 0) {
        collectorDiv = document.getElementById("div-via");
        collectorDiv.setAttribute("hidden", "");
    }

    if (document.getElementById("div-via").children.length < 8) {
        document.getElementById("add_via").disabled = false;
    }
}

function enableOtherField(checkbox) {
    otherDiv = document.getElementById('other_div')
    other = document.getElementById('id_other_field');
    if (checkbox.checked) {
        other.removeAttribute("disabled");
        otherDiv.removeAttribute("hidden");
        other.setAttribute("required", "");
    } else {
        other.setAttribute("disabled", "");
        otherDiv.setAttribute("hidden", "");
        other.removeAttribute("required");
    }


}

function changeRecurrance(radio) {
    div1 = document.getElementById('div-one-time');
    div2 = document.getElementById('div-recurring');

    if (radio.value == "oneTime") {
        div1.removeAttribute("hidden");
        div2.setAttribute("hidden", "");
    } else if (radio.value == "recurring") {
        div1.setAttribute("hidden", "");
        div2.removeAttribute("hidden");
    }
}

function changeReturn(radio) {
    returnTimes = document.getElementsByClassName('div-return');
    departureTimes = document.getElementsByClassName('div-departure');

    for (const item of returnTimes) {
        if (radio.value == "twoWay") {
            item.removeAttribute("hidden");
        } else if (radio.value == "oneWay") {
            item.setAttribute("hidden", "");
        }
    }

    switchTimes(departureTimes, radio);
    switchTimes(returnTimes, radio);
}

function switchTimes(times, radio) {
    for (const item of times) {
        inputs = item.getElementsByTagName('INPUT');
        if (radio.value == "oneWay") {
            // inputs[0].classList.add("select-lg")
            // inputs[0].classList.remove("select-xs")
            
        } else if (radio.value == "twoWay" && inputs[0].id != "id_returning_at_date_time") {
            // inputs[0].classList.add("select-xs")
            // inputs[0].classList.remove("select-lg")
        }
    }
}

function updateTheme(checked) {
    localStorage.setItem("theme", "dark");
    document.documentElement.setAttribute('data-theme', 'dark');

    if (checked) {
        localStorage.setItem("theme", "dark");
        document.documentElement.setAttribute('data-theme', 'dark');
    } else
        localStorage.setItem("theme", "light");
        document.documentElement.setAttribute('data-theme', 'light');
}

function loadTheme() {
    theme = localStorage["theme"];
    document.documentElement.setAttribute("data-theme", theme);
    
    switcher = document.getElementById("theme-switcher")
    if (theme == "dark") {
        switcher.checked = true;
    }
}

function updateMinDateTime(value) {
    returning_at = document.getElementById("id_returning_at_date_time");
    returning_at.min = value;
}

// The add ride page's transport options: one of them must be chosen, so they
// are all required until one is
function updateTransportRequired() {
    const options = document.querySelectorAll(".options");
    const chosen = [...options].some((option) => option.checked);
    for (const option of options) {
        option.required = !chosen;
    }
}

// Listened for on the document rather than on the elements, so that they
// also work on pages shown by Turbo (which replaces the page's elements)
document.addEventListener("change", (event) => {
    if (event.target.matches(".options")) {
        updateTransportRequired();
    }
    // Choosing a language in the side menu switches to it
    if (event.target.id === "id_language") {
        event.target.form.submit();
    }
});

function enableMaxPassengerField(checkbox) {
    otherDiv = document.getElementById('id_max_passengers_div')
    other = document.getElementById('id_max_passengers');
    if (checkbox.checked) {
        other.removeAttribute("disabled");
        otherDiv.removeAttribute("hidden");
        other.setAttribute("required", "");
    } else {
        other.setAttribute("disabled", "");
        otherDiv.setAttribute("hidden", "");
        other.removeAttribute("required");
    }
}



function debounce(func, delay) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => func.apply(this, args), delay);
    };
}

// Destination picker: a dropdown of the LUT campuses, whose place data is
// already known (campuses_id is the id of a json_script element), so choosing
// one makes no Google API query. "Other destination" shows the normal
// autocomplete input instead. The selected place is submitted as
// destination_json, the same as with autocomplete_init.
// If required_hint is given, a destination must be chosen before submitting.
// With optional, no destination is needed, but text typed into "Other
// destination" must still be turned into a place from the suggestions.
// initial_place selects a place to start with: its campus, or "Other
// destination" with the place filled in.
async function destination_init(div_id, campuses_id, placeholder, other_label, required_hint = null, optional = false, initial_place = null) {
    const dest_div = document.getElementById(div_id);
    const campuses = JSON.parse(document.getElementById(campuses_id).textContent);

    const fixedHeight = dest_div.classList.contains("h-12");
    dest_div.classList.remove("skeleton", "h-12");
    dest_div.classList.add("flex", "flex-col", "gap-2");
    const required = Boolean(required_hint) && !optional;

    const select = document.createElement('select');
    select.className = `select w-full ${fixedHeight ? "h-12" : ""}`;
    const placeholderOption = new Option(placeholder, "", true, true);
    // When a destination is required, the placeholder cannot be chosen
    placeholderOption.disabled = required;
    select.add(placeholderOption);
    campuses.forEach((campus, index) => select.add(new Option(campus.label, String(index))));
    select.add(new Option(other_label, "other"));
    dest_div.appendChild(select);

    if (required) {
        select.required = true;
        select.classList.add("validator");
        const validatorHint = document.createElement('p');
        validatorHint.className = "hidden validator-hint ml-3";
        validatorHint.textContent = required_hint;
        dest_div.appendChild(validatorHint);
    }

    // Holds the selected campus. Disabled inputs are not submitted, so only
    // one of this and the autocomplete's input is ever sent.
    const campusInfo = document.createElement('input');
    campusInfo.type = "hidden";
    campusInfo.name = "destination_json";
    campusInfo.disabled = true;
    dest_div.appendChild(campusInfo);

    // The autocomplete for "Other destination" is only created when needed
    const otherDiv = document.createElement('div');
    otherDiv.id = `${div_id}-other`;
    if (fixedHeight) {
        otherDiv.classList.add("h-12");
    }
    otherDiv.hidden = true;
    dest_div.appendChild(otherDiv);
    let otherReady = null;

    // Hidden and disabled inputs are also skipped by form validation
    function showOther(show) {
        otherDiv.hidden = !show;
        for (const input of otherDiv.querySelectorAll("input")) {
            input.disabled = !show;
        }
    }

    select.addEventListener("change", async (event) => {
        if (select.value === "other") {
            campusInfo.disabled = true;
            campusInfo.value = "";
            if (!otherReady) {
                otherReady = autocomplete_init(otherDiv.id, "destination", placeholder, required_hint, optional, otherInitial);
                // Lets other code wait for the autocomplete input to exist
                otherDiv.ready = otherReady;
            }
            showOther(true);
            await otherReady;
            // The selection may have changed while the autocomplete was loading
            if (select.value === "other") {
                showOther(true);
                // Only when the user chose it, not when set from code
                if (event.isTrusted) {
                    otherDiv.querySelector('input[type="text"]').focus();
                }
            }
        } else {
            showOther(false);
            const campus = campuses[select.value];
            campusInfo.value = campus ? JSON.stringify(campus.place) : "";
            campusInfo.disabled = !campus;
        }
    });

    // Start with initial_place selected
    let otherInitial = null;
    if (initial_place) {
        const index = campuses.findIndex((campus) => campus.place.id === initial_place.id);
        if (index === -1) {
            otherInitial = initial_place;
        }
        select.value = index === -1 ? "other" : String(index);
        select.dispatchEvent(new Event("change"));
    }
}

// If required_hint is given, the form cannot be submitted until a place
// has been selected from the suggestions, and the hint is shown under the input.
// With optional, the input may also be left empty, but any text in it must
// still be turned into a place from the suggestions.
// initial_place (a place as submitted in <id>_json) starts the input with
// that place selected, e.g. when editing a ride.
async function autocomplete_init(div_id, id, placeholder, required_hint = null, optional = false, initial_place = null) {
    const dest_div = document.getElementById(div_id);
    // console.log(dest_div);

    // Request needed libraries.
    const { AutocompleteSessionToken, AutocompleteSuggestion } =
        await google.maps.importLibrary('places');

    // The PlaceAutocompleteElement widget queries the API on every keystroke,
    // so we use our own input and only query once the user stops typing.
    dest_div.style.position = "relative";
    // The placeholder skeleton is no longer needed, and a fixed height on the
    // container would cut off the validator hint, so move it to the input.
    const inputHeight = dest_div.classList.contains("h-12") ? "h-12" : "";
    dest_div.classList.remove("skeleton", "h-12");

    const placeInput = document.createElement('input');
    placeInput.type = "text";
    placeInput.autocomplete = "off";
    placeInput.className = `input w-full ${inputHeight}`;
    placeInput.setAttribute("placeholder", placeholder);
    dest_div.appendChild(placeInput);

    const validatorHint = document.createElement('p');
    if (required_hint) {
        placeInput.classList.add("validator");
        placeInput.required = !optional;
        validatorHint.className = "hidden validator-hint ml-3";
        validatorHint.textContent = required_hint;
        dest_div.appendChild(validatorHint);
    }

    function updateValidity() {
        if (required_hint) {
            const missing = !selectedPlaceInfo.value && (!optional || placeInput.value.trim() !== "");
            placeInput.setCustomValidity(missing ? required_hint : "");
        }
    }

    const suggestionList = document.createElement('ul');
    suggestionList.className = "menu bg-base-100 rounded-field shadow-sm w-full";
    suggestionList.style.position = "absolute";
    suggestionList.style.left = "0";
    suggestionList.style.zIndex = "50";
    suggestionList.setAttribute("hidden", "");
    dest_div.appendChild(suggestionList);

    const selectedPlaceInfo = document.createElement('input');
    selectedPlaceInfo.setAttribute("hidden", "hidden");
    selectedPlaceInfo.id = `id_${id}_json`;
    selectedPlaceInfo.name = `${id}_json`
    selectedPlaceInfo.textContent = '';
    dest_div.appendChild(selectedPlaceInfo);
    if (initial_place) {
        placeInput.value = initial_place.displayName ?? "";
        selectedPlaceInfo.value = JSON.stringify(initial_place);
    }
    updateValidity();

    let sessionToken = new AutocompleteSessionToken();
    // Used to ignore responses to requests that have since been superseded.
    let requestCount = 0;

    function hideSuggestions() {
        suggestionList.replaceChildren();
        suggestionList.setAttribute("hidden", "");
    }

    async function selectPlace(placePrediction) {
        hideSuggestions();
        placeInput.value = placePrediction.text.toString();

        const place = placePrediction.toPlace();
        await place.fetchFields({
            fields: ['displayName', 'formattedAddress', 'location'],
        });
        selectedPlaceInfo.value = JSON.stringify(
            place.toJSON(),
            /* replacer */ null,
            /* space */ 2
        );
        updateValidity();
        // A session ends once a place is selected.
        sessionToken = new AutocompleteSessionToken();
    }

    const fetchSuggestions = debounce(async () => {
        const query = placeInput.value.trim();
        const requestId = ++requestCount;
        if (!query) {
            hideSuggestions();
            return;
        }

        const { suggestions } =
            await AutocompleteSuggestion.fetchAutocompleteSuggestions({
                input: query,
                includedRegionCodes: ['fi'],
                sessionToken: sessionToken,
            });
        if (requestId !== requestCount) {
            return;
        }

        suggestionList.replaceChildren();
        for (const { placePrediction } of suggestions) {
            if (!placePrediction) {
                continue;
            }
            const item = document.createElement('li');
            const link = document.createElement('a');
            link.textContent = placePrediction.text.toString();
            // mousedown fires before the input's blur, so the list is still there.
            link.addEventListener('mousedown', (event) => {
                event.preventDefault();
                selectPlace(placePrediction);
            });
            item.appendChild(link);
            suggestionList.appendChild(item);
        }
        if (suggestionList.children.length > 0) {
            // Directly under the input, above the validator hint
            suggestionList.style.top = `${placeInput.offsetHeight}px`;
            suggestionList.removeAttribute("hidden");
        } else {
            suggestionList.setAttribute("hidden", "");
        }
    }, 1000);

    placeInput.addEventListener('input', () => {
        // The text no longer matches the previously selected place.
        selectedPlaceInfo.value = '';
        updateValidity();
        fetchSuggestions();
    });
    placeInput.addEventListener('blur', hideSuggestions);
    placeInput.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            hideSuggestions();
        }
    });
}

// Images that start hidden inside a daisyUI skeleton call this from their
// onload/onerror attributes. The image is faded in and the skeleton removed.
// (Using the attributes means images that load before any script runs, e.g.
// from the cache, are still handled.)
function imageLoaded(img) {
    img.parentElement.classList.remove("skeleton");
    if (img.complete && img.naturalWidth > 0) {
        img.style.opacity = 1;
    }
}

// Called right after a profile photo's <img> (see _avatar.html). A photo the
// browser already has, e.g. the navbar's on every page, is shown at once
// instead of replaying the skeleton and fade-in each time.
function showIfCached(img) {
    if (img.complete && img.naturalWidth > 0) {
        img.classList.remove("transition-opacity");
        imageLoaded(img);
    }
}

// Cmd+Enter (Mac) or Ctrl+Enter (elsewhere) submits the form being filled in,
// as if its submit button was clicked: the browser checks required fields
// and the page's own submit handlers run (e.g. the search page's).
// - Only from fields typed or chosen in, never from a focused button, so
//   e.g. a request's Accept / Decline buttons cannot be pressed by accident.
// - Forms marked data-no-submit-shortcut are left out (e.g. deleting the
//   account, the language picker).
const IS_MAC = /Mac|iPhone|iPad/.test(navigator.userAgentData?.platform ?? navigator.platform);
const SHORTCUT_FIELD_TYPES_LEFT_OUT = ["button", "submit", "reset", "image", "file", "hidden"];

function shortcutSubmitButtons(form) {
    return [...form.elements].filter((element) => element.type === "submit");
}

document.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.repeat || event.isComposing) return;
    if (!(IS_MAC ? event.metaKey : event.ctrlKey) || event.altKey || event.shiftKey) return;

    const field = document.activeElement;
    const form = field?.form;
    if (!form || form.matches("[data-no-submit-shortcut]") || form.method === "dialog") return;
    if (field.tagName === "BUTTON" || SHORTCUT_FIELD_TYPES_LEFT_OUT.includes(field.type)) return;

    event.preventDefault();
    // With a single submit button, submit as if it was clicked (its name and
    // value are sent). With several, e.g. the search page's page buttons,
    // submit without one.
    const buttons = shortcutSubmitButtons(form);
    if (buttons.length === 1) {
        if (!buttons[0].disabled) form.requestSubmit(buttons[0]);
    } else {
        form.requestSubmit();
    }
});

// Submit buttons show the shortcut when hovered
document.addEventListener("DOMContentLoaded", () => {
    const hint = IS_MAC ? "⌘ + Enter" : "Ctrl + Enter";
    for (const form of document.forms) {
        if (form.matches("[data-no-submit-shortcut]") || form.method === "dialog") continue;
        for (const button of shortcutSubmitButtons(form)) {
            if (!button.title) button.title = hint;
        }
    }
});
