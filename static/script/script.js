// ========== СИСТЕМА УВЕДОМЛЕНИЙ ==========
document.addEventListener('DOMContentLoaded', function() {
    // Показываем flash-сообщения как уведомления
    const flashMessages = document.querySelectorAll('#flash-messages div');
    flashMessages.forEach(function(msg) {
        const category = msg.dataset.category;
        const message = msg.dataset.message;
        showNotification(message, category);
    });
    
    // Инициализация поиска
    initSearch();
});

function showNotification(message, type = 'info', title = null) {
    const container = document.getElementById('notifications-container');
    
    const icons = {
        'success': 'fa-check-circle',
        'danger': 'fa-times-circle',
        'warning': 'fa-exclamation-triangle',
        'info': 'fa-info-circle'
    };
    
    const titles = {
        'success': title || 'Успешно',
        'danger': title || 'Ошибка',
        'warning': title || 'Внимание',
        'info': title || 'Информация'
    };
    
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <div class="notification-icon">
            <i class="fas ${icons[type] || icons['info']}"></i>
        </div>
        <div class="notification-content">
            <div class="notification-title">${titles[type] || titles['info']}</div>
            <div class="notification-message">${message}</div>
        </div>
        <button class="notification-close" onclick="closeNotification(this.parentElement)">
            <i class="fas fa-times"></i>
        </button>
        <div class="notification-progress">
            <div class="notification-progress-bar"></div>
        </div>
    `;
    
    container.appendChild(notification);
    
    // Автоматическое закрытие через 5 секунд
    const autoClose = setTimeout(() => {
        closeNotification(notification);
    }, 5000);
    
    // Сохраняем таймер в элементе
    notification._timeout = autoClose;
    
    // При наведении останавливаем таймер
    notification.addEventListener('mouseenter', () => {
        clearTimeout(notification._timeout);
        const progressBar = notification.querySelector('.notification-progress-bar');
        if (progressBar) {
            progressBar.style.animationPlayState = 'paused';
        }
    });
    
    notification.addEventListener('mouseleave', () => {
        const progressBar = notification.querySelector('.notification-progress-bar');
        if (progressBar) {
            progressBar.style.animationPlayState = 'running';
        }
        notification._timeout = setTimeout(() => {
            closeNotification(notification);
        }, 3000);
    });
}

function closeNotification(notification) {
    clearTimeout(notification._timeout);
    notification.classList.add('removing');
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 400);
}

// ========== ПОИСК ==========
function initSearch() {
    const searchInput = document.getElementById('main-search');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            const query = this.value.trim();
            
            const resultsDiv = document.getElementById('search-results');
            if (!resultsDiv) return;
            
            if (query.length < 2) {
                resultsDiv.innerHTML = '';
                resultsDiv.style.display = 'none';
                return;
            }
            
            searchTimeout = setTimeout(() => {
                fetch(`/api/hotels/search?q=${encodeURIComponent(query)}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.length === 0) {
                            resultsDiv.innerHTML = '<div class="search-result-item">Ничего не найдено</div>';
                        } else {
                            resultsDiv.innerHTML = data.map(hotel => `
                                <div class="search-result-item" onclick="window.location.href='/hotel/${hotel.id}'">
                                    <strong>${hotel.name}</strong>
                                    <span>${hotel.city}, ${hotel.country} ★${hotel.stars}</span>
                                    <span class="price">от ${hotel.min_price.toLocaleString()} ₽/ночь</span>
                                </div>
                            `).join('');
                        }
                        resultsDiv.style.display = 'block';
                    })
                    .catch(error => console.error('Error:', error));
            }, 300);
        });
        
        document.addEventListener('click', function(e) {
            const resultsDiv = document.getElementById('search-results');
            if (resultsDiv && searchInput && !searchInput.contains(e.target)) {
                resultsDiv.style.display = 'none';
            }
        });
    }
}

// ========== ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ ==========
document.addEventListener('click', function(e) {
    if (e.target.closest('.btn-delete') && !e.target.closest('.btn-delete').hasAttribute('onclick')) {
        if (!confirm('Вы уверены, что хотите удалить этот элемент? Это действие нельзя отменить.')) {
            e.preventDefault();
        }
    }
});

// ========== ВАЛИДАЦИЯ ФОРМ ==========
document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', function(e) {
        const requiredFields = form.querySelectorAll('[required]');
        let isValid = true;
        
        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                field.style.borderColor = '#E74C3C';
                isValid = false;
            } else {
                field.style.borderColor = '#E8E8E8';
            }
        });
        
        if (!isValid) {
            e.preventDefault();
            showNotification('Пожалуйста, заполните все обязательные поля', 'warning');
        }
    });
});