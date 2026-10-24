// Aplica o tema salvo antes da primeira pintura. É só preferência visual, nunca dado de negócio.
(function () {
    try {
        var tema = localStorage.getItem('gflow-tema');
        if (tema === 'light' || tema === 'dark') document.documentElement.dataset.theme = tema;
    } catch (e) { /* storage indisponível: segue o sistema */ }
})();
