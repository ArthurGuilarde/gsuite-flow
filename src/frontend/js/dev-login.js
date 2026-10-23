const status = document.getElementById('dev-status');
let csrf;
try {
    const response = await fetch('/auth/dev/config', {credentials: 'same-origin', cache: 'no-store'});
    if (!response.ok) throw new Error('Login local indisponível.');
    const config = await response.json();
    csrf = config.csrf_token;
    for (const user of config.users) {
        const option = document.createElement('option');
        option.value = user.id; option.textContent = user.name;
        document.getElementById('dev-user').append(option);
    }
} catch (error) { status.textContent = error.message; }
document.getElementById('dev-login').addEventListener('submit', async event => {
    event.preventDefault();
    const response = await fetch('/auth/dev/login', {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf ?? ''},
        body: JSON.stringify({user_id: document.getElementById('dev-user').value})
    });
    if (response.ok) location.replace('/');
    else status.textContent = 'Não foi possível entrar no modo local.';
});
