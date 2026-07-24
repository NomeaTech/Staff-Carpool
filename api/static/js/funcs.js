function viaAdd() {
    // viaInput = document.getElementById("via-input");
    inputDiv = document.getElementById("div-via");
    inputDiv.removeAttribute("hidden", "");
    inputDiv.insertAdjacentHTML('beforeend', '<input id="via-input" class="input w-full" placeholder="Via">');

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

    for (const item of departureTimes) {
        selects = item.getElementsByTagName('SELECT');
        if (radio.value == "oneWay") {
            selects[0].classList.add("select-lg")
            selects[0].classList.remove("select-xs")
            
            selects[1].classList.add("select-lg")
            selects[1].classList.remove("select-xs")
            
        } else if (radio.value == "twoWay") {
            selects[0].classList.add("select-xs")
            selects[0].classList.remove("select-lg")
            
            selects[1].classList.add("select-xs")
            selects[1].classList.remove("select-lg")
        }
    }
    // times.forEach(timeIter(radio));
}