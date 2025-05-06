document.getElementById('temperatureSlider').addEventListener('input', function () {
    const temp = parseFloat(this.value).toFixed(2);
    document.getElementById('tempLabel').textContent = "Temperature: " + temp;
    // Future: send temp to backend
});

function sendMainCommand() {
    const cmd = document.getElementById("mainCommand").value;
    document.getElementById("statusOutput").innerText = "Sent main command: " + cmd;
    // TODO: POST to FastAPI later
}

function sendCorrection() {
    const msg = document.getElementById("correctionMsg").value;
    document.getElementById("statusOutput").innerText = "Sent correction message: " + msg;
    // TODO: POST to FastAPI later
}
