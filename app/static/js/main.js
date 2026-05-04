// main.js — JavaScript base da aplicação

document.addEventListener('DOMContentLoaded', function() {
    // Auto-fechar alertas após 5 segundos
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transition = 'opacity 0.3s ease-out';
            setTimeout(() => {
                alert.remove();
            }, 300);
        }, 5000);
    });
});

// Função auxiliar para fazer requisições AJAX
function apiRequest(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    return fetch(url, options).then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    });
}

// Confirmar ação com diálogo
function confirmar(mensagem) {
    return confirm(mensagem);
}

// Copiar para clipboard
function copiarParaArea(texto) {
    navigator.clipboard.writeText(texto).then(() => {
        alert('Copiado para a área de transferência!');
    }).catch(err => {
        console.error('Erro ao copiar:', err);
    });
}

// Formatação de data
function formatarData(data) {
    const d = new Date(data);
    return d.toLocaleDateString('pt-BR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    });
}

// Formatação de hora
function formatarHora(data) {
    const d = new Date(data);
    return d.toLocaleTimeString('pt-BR', {
        hour: '2-digit',
        minute: '2-digit'
    });
}
