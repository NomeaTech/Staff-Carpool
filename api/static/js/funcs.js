function viaAdd() {
    // viaInput = document.getElementById("via-input");
    inputDiv = document.getElementById("div-via");
    inputDiv.removeAttribute("hidden", "");

    id = Date.now().toString(36) + Math.floor(Math.pow(10, 12) + Math.random() * 9*Math.pow(10, 12)).toString(36)
    inputDiv.insertAdjacentHTML(
        'beforeend', 
        `<div class="grid grid-cols-5 col-span-5 gap-4 div-via-input" id="${id}-div">
            <input id="id_via_input${id}" name="via_input_${id}" class="input w-full col-span-4" placeholder="Via">
            <button id="${id}-button" data-idref="${id}" class="btn btn-error col-span-1" onclick="viaRemove(this)" type="button">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" fill="currentColor" stroke="currentColor" class="scale-120"><!--!Font Awesome Free v7.3.1 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M96 320C96 302.3 110.3 288 128 288L512 288C529.7 288 544 302.3 544 320C544 337.7 529.7 352 512 352L128 352C110.3 352 96 337.7 96 320z"/></svg>
            </button>
        </div>`
    );
}

function viaRemove(element) {
    div = document.getElementById(`${element.dataset.idref}-div`);
    div.remove()

    vias = document.getElementsByClassName("div-via-input");
    if (vias.length == 0) {
        collectorDiv = document.getElementById("div-via");
        collectorDiv.setAttribute("hidden", "");
    }
}

function enableOtherField(checkbox) {
    otherDiv = document.getElementById('other_div')
    other = document.getElementById('id_other_field');
    if (checkbox.checked) {
        other.removeAttribute("disabled");
        otherDiv.removeAttribute("hidden");
    } else {
        other.setAttribute("disabled", "");
        otherDiv.setAttribute("hidden", "");
    }


}

function changeRecurrance(radio) {
    div1 = document.getElementById('div-one-time');
    div2 = document.getElementById('div-recurring');
    // var days = ["Mon."]


    // if (div2.innerHTML === "") {
    //     for 
    // }

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
            inputs[0].classList.add("select-lg")
            inputs[0].classList.remove("select-xs")
            
        } else if (radio.value == "twoWay" && inputs[0].id != "id_returning_at_date_time") {
            inputs[0].classList.add("select-xs")
            inputs[0].classList.remove("select-lg")
        }
    }
}