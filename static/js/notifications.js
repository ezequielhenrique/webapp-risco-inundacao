function showAlert(message, type = "error") {
    const container = document.getElementById("alert-container");

    const alert = document.createElement("div");
    alert.classList.add("alert");
    if (type === "success") alert.classList.add("success");

    alert.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove()">×</button>
    `;

    container.appendChild(alert);

    // auto remove depois de 5s
    //setTimeout(() => {
    //    alert.remove();
    //}, 5000);
}
