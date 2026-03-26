// Глобальные переменные
let currentTariff = null;
let currentHotelId = null;
let notificationQueue = [];
let isShowingNotification = false;

// Инициализация при загрузке страницы
$(document).ready(function() {
    // Инициализация уведомлений
    initializeNotifications();

    // Инициализация обработчиков для кнопок бронирования
    $('.btn-book').click(function() {
        const tariffId = $(this).data('tariff-id');
        const tariffName = $(this).data('tariff-name');
        const price = $(this).data('price');
        currentTariff = { id: tariffId, name: tariffName, price: price };
        currentHotelId = window.location.pathname.split('/').pop();

        $('#tariffName').val(tariffName);
        $('#bookingModal').modal('show');
    });

    // Расчет стоимости при изменении дат
    $('#checkIn, #checkOut').change(calculateTotalPrice);
    $('#guests').change(calculateTotalPrice);

    // Подтверждение бронирования
    $('#confirmBooking').click(confirmBooking);

    // Анимация для карточек
    $('.hotel-card, .tariff-card').hover(
        function() { $(this).css('transform', 'translateY(-5px)'); },
        function() { $(this).css('transform', 'translateY(0)'); }
    );
});

// Функция инициализации уведомлений
function initializeNotifications() {
    // Автоматическое отображение всех уведомлений
    $('.notification-toast').each(function() {
        const toast = new bootstrap.Toast(this, {
            autohide: true,
            delay: 3000
        });
        toast.show();

        // Удаление уведомления после скрытия
        $(this).on('hidden.bs.toast', function() {
            $(this).remove();
        });
    });
}

// Функция отображения уведомлений (без дублирования)
function showNotification(message, type = 'info') {
    // Проверяем, не показывается ли уже такое же уведомление
    const existingNotifications = $('.notification-toast .toast-body');
    let isDuplicate = false;

    existingNotifications.each(function() {
        if ($(this).text() === message) {
            isDuplicate = true;
            return false;
        }
    });

    if (isDuplicate) {
        return;
    }

    // Создаем новое уведомление
    const icon = getIconForType(type);
    const notificationHtml = `
        <div class="toast notification-toast ${type}" role="alert" aria-live="assertive" aria-atomic="true" data-bs-autohide="true" data-bs-delay="3000">
            <div class="toast-header">
                <i class="${icon} me-2"></i>
                <strong class="me-auto">Уведомление</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;

    $('.toast-container').append(notificationHtml);
    const toastElement = $('.toast-container .notification-toast').last();
    const toast = new bootstrap.Toast(toastElement[0], {
        autohide: true,
        delay: 3000
    });

    toast.show();

    // Удаляем уведомление после скрытия
    toastElement.on('hidden.bs.toast', function() {
        $(this).remove();
    });
}

// Функция получения иконки для типа уведомления
function getIconForType(type) {
    switch(type) {
        case 'success':
            return 'fas fa-check-circle';
        case 'danger':
            return 'fas fa-exclamation-circle';
        case 'warning':
            return 'fas fa-exclamation-triangle';
        case 'info':
            return 'fas fa-info-circle';
        default:
            return 'fas fa-bell';
    }
}

// Функция расчета общей стоимости
function calculateTotalPrice() {
    if (!currentTariff) return;

    const checkIn = $('#checkIn').val();
    const checkOut = $('#checkOut').val();
    const guests = parseInt($('#guests').val()) || 1;

    if (checkIn && checkOut) {
        const start = new Date(checkIn);
        const end = new Date(checkOut);
        const nights = Math.ceil((end - start) / (1000 * 60 * 60 * 24));

        if (nights > 0) {
            const total = nights * currentTariff.price;
            $('#totalPrice').val(total + ' ₽');
        } else {
            $('#totalPrice').val('Некорректные даты');
            showNotification('Дата выезда должна быть позже даты заезда', 'warning');
        }
    }
}

// Функция подтверждения бронирования
function confirmBooking() {
    const checkIn = $('#checkIn').val();
    const checkOut = $('#checkOut').val();
    const guests = $('#guests').val();

    if (!checkIn || !checkOut) {
        showNotification('Пожалуйста, выберите даты заезда и выезда', 'warning');
        return;
    }

    const start = new Date(checkIn);
    const end = new Date(checkOut);

    if (end <= start) {
        showNotification('Дата выезда должна быть позже даты заезда', 'warning');
        return;
    }

    // Отправка запроса на бронирование
    $.ajax({
        url: `/book/${currentHotelId}`,
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            tariff_id: currentTariff.id,
            check_in: checkIn,
            check_out: checkOut,
            guests: guests
        }),
        success: function(response) {
            if (response.success) {
                showNotification('Бронирование успешно создано!', 'success');
                $('#bookingModal').modal('hide');
                setTimeout(function() {
                    window.location.href = '/dashboard';
                }, 2000);
            }
        },
        error: function(xhr) {
            if (xhr.status === 401) {
                showNotification('Пожалуйста, войдите в систему', 'warning');
                setTimeout(function() {
                    window.location.href = '/login';
                }, 2000);
            } else {
                showNotification('Произошла ошибка при бронировании. Попробуйте позже', 'danger');
            }
        }
    });
}

// Валидация форм
function validateForm(formId) {
    const form = $('#' + formId);
    let isValid = true;

    form.find('input[required], select[required], textarea[required]').each(function() {
        if (!$(this).val()) {
            $(this).addClass('is-invalid');
            isValid = false;
            showNotification('Пожалуйста, заполните все обязательные поля', 'warning');
        } else {
            $(this).removeClass('is-invalid');
        }
    });

    return isValid;
}

// Автозаполнение дат для бронирования (минимальная дата - сегодня)
$('#checkIn, #checkOut').attr('min', new Date().toISOString().split('T')[0]);

// Обработка удаления тарифов в админке
function removeTariff(button) {
    if (confirm('Вы уверены, что хотите удалить этот тариф?')) {
        $(button).closest('.tariff-item').remove();
        showNotification('Тариф удален', 'info');
    }
}

// Предпросмотр изображения отеля
function previewImage(input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
            $('#imagePreview').attr('src', e.target.result);
            showNotification('Изображение загружено', 'success');
        };
        reader.readAsDataURL(input.files[0]);
    }
}

// Поиск отелей
function searchHotels() {
    const searchTerm = $('#searchInput').val().toLowerCase();
    let foundCount = 0;

    $('.hotel-card').each(function() {
        const hotelName = $(this).find('.card-title').text().toLowerCase();
        const hotelCity = $(this).find('.card-text:first').text().toLowerCase();

        if (hotelName.includes(searchTerm) || hotelCity.includes(searchTerm)) {
            $(this).parent().show();
            foundCount++;
        } else {
            $(this).parent().hide();
        }
    });

    if (searchTerm && foundCount === 0) {
        showNotification('По вашему запросу ничего не найдено', 'info');
    }
}

// Фильтрация по цене
function filterByPrice() {
    const maxPrice = $('#priceFilter').val();
    let foundCount = 0;

    $('.tariff-card').each(function() {
        const priceText = $(this).find('h3').text();
        const price = parseFloat(priceText);
        if (price <= maxPrice) {
            $(this).show();
            foundCount++;
        } else {
            $(this).hide();
        }
    });

    if (maxPrice && foundCount === 0) {
        showNotification(`Нет тарифов дороже ${maxPrice} ₽`, 'info');
    }
}

// Добавление эффекта загрузки для кнопок
$('form').submit(function() {
    const submitBtn = $(this).find('button[type="submit"]');
    if (submitBtn.length) {
        submitBtn.prop('disabled', true);
        const originalText = submitBtn.html();
        submitBtn.html('<span class="spinner-border spinner-border-sm"></span> Загрузка...');

        // Сохранение оригинального текста
        submitBtn.data('original-text', originalText);

        // Восстановление кнопки через 10 секунд на случай ошибки
        setTimeout(function() {
            if (submitBtn.prop('disabled')) {
                submitBtn.prop('disabled', false);
                submitBtn.html(submitBtn.data('original-text') || originalText);
                showNotification('Превышено время ожидания. Попробуйте еще раз', 'warning');
            }
        }, 10000);
    }
});

// Анимация при прокрутке
$(window).scroll(function() {
    const scrollPos = $(window).scrollTop();
    $('.hero-section').css('opacity', 1 - scrollPos / 500);
});

// Обработка выбора тарифа
$('.tariff-card').click(function() {
    $(this).addClass('selected');
    setTimeout(function() {
        $('.tariff-card').removeClass('selected');
    }, 500);
});

// Инициализация всех tooltips
var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
var tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
});

// Глобальная функция для показа уведомлений (доступна из любого места)
window.showNotification = showNotification;