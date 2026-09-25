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
            <div class="col-span-4 w-full">
                <input id="id_via_input${id}" name="via_input_${id}" class="digitrans_autocomplete input" placeholder="Via" value=${via_value}>
            </div>
            <button id="${id}-button" data-idref="${id}" class="btn btn-error col-span-1" onclick="viaRemove(this)" type="button">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" fill="currentColor" stroke="currentColor" class="scale-120"><!--!Font Awesome Free v7.3.1 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M96 320C96 302.3 110.3 288 128 288L512 288C529.7 288 544 302.3 544 320C544 337.7 529.7 352 512 352L128 352C110.3 352 96 337.7 96 320z"/></svg>
            </button>
        </div>`
    );

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

// Digitransit reverse-geocoding autocomplete (attach to inputs by class)
(function() {
    function ensureDatalist(input) {
        var listId = 'digitrans_autocomplete_list';
        var dl = document.getElementById(listId);
        if (!dl) {
            dl = document.createElement('datalist');
            dl.id = listId;
            if (input && input.parentNode) input.parentNode.appendChild(dl);
            else document.body.appendChild(dl);
        }
        input.setAttribute('list', listId);
        return dl;
    }
    // helper to attach behavior to a single input element
    function attachAutocompleteTo(input) {
        if (!input || input._digitransAttached) return;
        input._digitransAttached = true;

        // create a dropdown container unique to this input
        var wrapper = document.createElement('div');
        wrapper.className = 'digitrans-autocomplete-wrapper';
        wrapper.style.position = 'relative';

        // ensure input's parent is positioned so absolute dropdown aligns
        var parent = input.parentNode;
        if (parent && window.getComputedStyle(parent).position === 'static') {
            parent.style.position = 'relative';
        }

        var dropdown = document.createElement('ul');
        dropdown.className = 'digitrans-suggestions hidden absolute left-0 right-0 mt-1 z-50 bg-base-100 shadow rounded overflow-auto';
        dropdown.style.maxHeight = '240px';
        dropdown.style.listStyle = 'none';
        dropdown.style.margin = '0';
        dropdown.style.padding = '0';
        dropdown.style.cursor = 'pointer';

        // insert dropdown after input
        if (input.nextSibling) parent.insertBefore(dropdown, input.nextSibling);
        else parent.appendChild(dropdown);

        var timer = null;
        var lastXhr = null;
        var selectedIndex = -1;
        var lastFeatures = [];
        // hidden input for storing selected feature JSON
        var featureInputId = 'feature_json_' + input.id;
        var featureInputName = 'feature_' + input.id;
        var hiddenFeatureInput = document.getElementById(featureInputId);
        if (!hiddenFeatureInput) {
            hiddenFeatureInput = document.createElement('input');
            hiddenFeatureInput.type = 'hidden';
            hiddenFeatureInput.id = featureInputId;
            hiddenFeatureInput.name = featureInputName;
            if (input.nextSibling) parent.insertBefore(hiddenFeatureInput, input.nextSibling.nextSibling);
            else parent.appendChild(hiddenFeatureInput);
        }

        function clearSuggestions() {
            dropdown.innerHTML = '';
            dropdown.classList.add('hidden');
            selectedIndex = -1;
        }

        function renderSuggestions(features) {
            dropdown.innerHTML = '';
            if (!features || features.length === 0) {
                clearSuggestions();
                return;
            }

            lastFeatures = features;

            features.forEach(function(f, idx) {
                var props = f.properties || {};
                var label = props.label || props.name || f.text || '';
                if (!label) return;
                var li = document.createElement('li');
                li.className = 'digitrans-suggestion px-3 py-2 hover:bg-base-200';
                li.setAttribute('data-index', idx);
                li.textContent = label;
                li.addEventListener('mousedown', function(e) {
                    // mousedown so it fires before blur
                    e.preventDefault();
                    input.value = label;
                    // store feature JSON
                    try {
                        var feat = lastFeatures[idx] || null;
                        hiddenFeatureInput.value = feat ? JSON.stringify(feat) : '';
                    } catch (err) {
                        console.error('Failed to serialize feature', err);
                        hiddenFeatureInput.value = '';
                    }
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    clearSuggestions();
                });
                dropdown.appendChild(li);
            });
            dropdown.classList.remove('hidden');
        }

        input.addEventListener('input', function() {
            var q = this.value.trim();
            if (timer) clearTimeout(timer);
            if (q.length < 3) {
                clearSuggestions();
                if (lastXhr && lastXhr.readyState !== 4) lastXhr.abort();
                return;
            }

            timer = setTimeout(function() {
                if (lastXhr && lastXhr.readyState !== 4) lastXhr.abort();
                lastXhr = $.ajax({
                    url: input.dataset.digitransProxyUrl || '/app/digitrans/autocomplete/',
                    method: 'GET',
                    data: {
                        text: q,
                        size: input.dataset.digitransSize || 7
                    },
                    dataType: 'json',
                    success: function(resp) {
                        try {
                            var features = resp && resp.features ? resp.features : [];
                            renderSuggestions(features);
                        } catch (e) {
                            console.error('Digitransit parse error', e);
                            clearSuggestions();
                        }
                    },
                    error: function(xhr, status, err) {
                        if (status !== 'abort') console.error('Digitransit proxy request failed', status, err);
                        clearSuggestions();
                    }
                });
            }, parseInt(input.dataset.digitransDebounce || 250, 10));
        });

        input.addEventListener('keydown', function(e) {
            var items = dropdown.querySelectorAll('.digitrans-suggestion');
            if (!items || items.length === 0) return;
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
                items.forEach(function(it, i) { it.classList.toggle('bg-base-200', i === selectedIndex); });
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                selectedIndex = Math.max(selectedIndex - 1, 0);
                items.forEach(function(it, i) { it.classList.toggle('bg-base-200', i === selectedIndex); });
            } else if (e.key === 'Enter') {
                if (selectedIndex >= 0 && items[selectedIndex]) {
                        e.preventDefault();
                        var label = items[selectedIndex].textContent;
                        input.value = label;
                        // set hidden feature input from lastFeatures[selectedIndex]
                        try {
                            var feat = lastFeatures[selectedIndex] || null;
                            hiddenFeatureInput.value = feat ? JSON.stringify(feat) : '';
                        } catch (err) {
                            console.error('Failed to serialize feature', err);
                            hiddenFeatureInput.value = '';
                        }
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                        clearSuggestions();
                    }
            } else if (e.key === 'Escape') {
                clearSuggestions();
            }
        });

        // hide on blur (allow click by delaying)
        input.addEventListener('blur', function() {
            setTimeout(clearSuggestions, 150);
        });
    }

    // attach to current inputs
    var inputs = document.querySelectorAll('.digitrans_autocomplete');
    inputs.forEach(function(i) { attachAutocompleteTo(i); });

    // observe for dynamically added inputs (e.g., added by other scripts)
    var observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(m) {
            m.addedNodes && m.addedNodes.forEach(function(node) {
                if (!node) return;
                if (node.nodeType === 1) {
                    if (node.classList && node.classList.contains('digitrans_autocomplete')) attachAutocompleteTo(node);
                    // also check descendants
                    var descendants = node.querySelectorAll && node.querySelectorAll('.digitrans_autocomplete');
                    if (descendants && descendants.length) descendants.forEach(function(d) { attachAutocompleteTo(d); });
                }
            });
        });
    });
    observer.observe(document.documentElement || document.body, { childList: true, subtree: true });
})();

