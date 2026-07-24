function viaAdd() {
    // viaInput = document.getElementById("via-input");
    inputDiv = document.getElementById("div-via");
    inputDiv.removeAttribute("hidden", "");

    id = Date.now().toString(36) + Math.floor(Math.pow(10, 12) + Math.random() * 9*Math.pow(10, 12)).toString(36)
    // console.log(id)
    inputDiv.insertAdjacentHTML(
        'beforeend', 
        `<div class="grid grid-cols-5 col-span-5 gap-4 div-via-input" id="${id}-div">
            <input class="input w-full col-span-4" placeholder="Via">
            <button id="${id}-button" data-idref="${id}" class="btn btn-error col-span-1 text-lg" onclick="viaRemove(this)" type="button">
                -
            </button>
        </div>`
    );

}

function viaRemove(element) {
    console.log(`remove ${element.dataset.idref}`);
    div = document.getElementById(`${element.dataset.idref}-div`);
    div.remove()

    vias = document.getElementsByClassName("div-via-input");
    if (vias.length == 0) {
        collectorDiv = document.getElementById("div-via");
        collectorDiv.setAttribute("hidden", "");
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