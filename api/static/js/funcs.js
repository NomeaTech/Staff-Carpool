function viaAdd(via_value = "") {
    count = $("#div-via").children().length;
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

    autocomplete_init(`div-autocomplete-via-${id}`, `via_${id}`, "Via");

    if (count >= 7) {
        $("#add_via").prop("disabled", true);
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

    count = $("#div-via").length
    if (count < 8) {
        $("#add_via").prop("disabled", false);
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

// $(function(){
//     $('.options').change(function(){
//         console.log(this);
//         var requiredCheckboxes = $('.options :checkbox[required]');
//         requiredCheckboxes.change(function(){
//             if(this.is(':checked')) {
//                 requiredCheckboxes.removeAttr('required');
//             } else {
//                 requiredCheckboxes.attr('required', 'required');
//             }
//         });
//     });
// });

$(function(){
    var requiredCheckboxes = $('.options');
    requiredCheckboxes.change(function(){
        if(requiredCheckboxes.is(':checked')) {
            requiredCheckboxes.removeAttr('required');
        } else {
            requiredCheckboxes.attr('required', '');
        }
    });
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

$(function() {
    $('#id_language').on('change', function() {
        $("#id_lang_form").submit();
    });
});

function debounce(func, delay) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => func.apply(this, args), delay);
    };
}

// If required_hint is given, the form cannot be submitted until a place
// has been selected from the suggestions, and the hint is shown under the input.
async function autocomplete_init(div_id, id, placeholder, required_hint = null) {
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
        placeInput.required = true;
        validatorHint.className = "hidden validator-hint ml-3";
        validatorHint.textContent = required_hint;
        dest_div.appendChild(validatorHint);
    }

    function updateValidity() {
        if (required_hint) {
            placeInput.setCustomValidity(selectedPlaceInfo.value ? "" : required_hint);
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