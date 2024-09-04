from transformers import pipeline
from bs4 import BeautifulSoup
import requests
import time

# Инициализация модели для анализа тональности
sentiment_pipeline = pipeline("sentiment-analysis", model="blanchefort/rubert-base-cased-sentiment")
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

# Ваш API ключ от NewsAPI
NEWS_API_KEY = 'abde548c17e14b56adcd1d8ae20bf083'
TELEGRAM_BOT_TOKEN = '7505061719:AAHjFDzUAoXeJ86myisHUJipHlDPNspJRgk'
TELEGRAM_CHAT_ID = '@russia_market_twits'

KEY_WORDS = [
    'Компания', 'прибыль', 'убыток', 'Выручка', 'Акции', 'Котировка', 'Рост', 'Снижение', 'Прогноз', 'Отчет',
    'Рынок', 'Инвестиции', 'Капитализация', 'Рентабельность', 'Сделка', 'Финансы', 'Банкротство', 'Кризис',
    'Дивиденды', 'Риски', 'Слияние', 'Поглощение', 'Рейтинги', 'Кредит', 'Доход', 'Партнерство', 'Регулирование',
    'Санкции', 'Налоги', 'Субсидии'
]


# Компании, по которым будем искать новости
COMPANIES = {
    'Газпром': 'GAZP',
    'Сбербанк': 'SBER',
    'Мечел': 'MTLR',
    'Озон': 'OZON',
    'ПИК': 'PIKK',
    'ALIBABA': 'BABA',
    'JD': 'JD'
}

# URLs для API
NEWS_URL = 'https://newsapi.org/v2/everything'

def fetch_article_content(url):
    """
    Функция для извлечения текста статьи по URL.
    """
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            paragraphs = soup.find_all('p')
            article_content = ' '.join([p.get_text() for p in paragraphs])
            return article_content
        else:
            print(f"Ошибка при запросе страницы: {response.status_code}")
            return None
    except Exception as e:
        print(f"Ошибка при извлечении статьи: {e}")
        return None


def generate_summary(article_content):
    """
    Функция для создания краткой сводки из текста статьи.
    """
    if article_content:
        summary = summarizer(article_content, max_length=150, min_length=30, do_sample=False)
        return summary[0]['summary_text']
    else:
        return "Не удалось получить содержимое статьи."

def analyze_news(news_description):
    # Подсчет ключевых слов в новости
    keyword_count = sum(1 for word in KEY_WORDS if word.lower() in news_description.lower())

    if keyword_count == 0:
        return False, None, None

    # Анализ тональности новости
    sentiment = sentiment_pipeline(news_description)[0]
    sentiment_label = sentiment['label']
    sentiment_score = sentiment['score']

    # Условия для проверки тональности и количества ключевых слов
    if keyword_count > 1 and (sentiment_label == 'NEGATIVE' or sentiment_label == 'POSITIVE'):
        return True, sentiment_label, sentiment_score, keyword_count
    return False, sentiment_label, sentiment_score, keyword_count


def is_news_related_to_company(news_text, company_name, ticker):
    # Проверяем наличие названия компании
    if company_name.lower() in news_text.lower():
        return True

    # Проверяем наличие тикера компании
    if ticker.lower() in news_text.lower():
        return True

    return False

def fetch_news(company):
    params = {
        'q': company,
        'qInTitle': company,
        'apiKey': NEWS_API_KEY,
        'language': 'ru',
        'sortBy': 'publishedAt',
        'pageSize': 20,  # Количество новостей, которое нужно вернуть
    }
    response = requests.get(NEWS_URL, params=params)
    if response.status_code == 200:
        return response.json()['articles']
    else:
        print(f"Ошибка при запросе новостей: {response.status_code}")
        return []

def fetch_stock_price(ticker):
    url = f'https://iss.moex.com/iss/engines/stock/markets/shares/securities/{ticker}.json'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        market_data = data['marketdata']['data'][0]
        last_price = market_data[12]  # Цена последней сделки
        return last_price
    else:
        print(f"Ошибка при запросе котировки: {response.status_code}")
        return None

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    params = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Ошибка при отправке сообщения: {response.status_code}")

def main():
    last_published = {}

    while True:
        for company, ticker in COMPANIES.items():
            news_array = fetch_news(company)
            if news_array:
                # Проверяем дату последней новости
                for news in reversed(news_array):
                    if last_published.get(company) != news['publishedAt'] and is_news_related_to_company(news_text=news['title'], company_name=company, ticker=ticker):

                        # title = news['title']
                        url = news['url']
                        published_at = news['publishedAt']
                        # description = news['description']
                        stock_price = fetch_stock_price(ticker)

                        article_content = fetch_article_content(url)
                        print(article_content)
                        result, sentiment_label, sentiment_score, count = analyze_news(article_content)
                        if not result:
                            continue

                        last_published[company] = published_at
                        description = generate_summary(article_content)

                        # Формируем сообщение для Telegram
                        message = f"<b>{company}</b>\n\n"
                        # message += f"📰 {title}\n\n"
                        message += f"🗓 <b>Дата публикации:</b> {published_at}\n\n"
                        message += f"💬 <b>Описание:</b> {description}\n"
                        message += f"📊 <b>Тональность:</b> {sentiment_label} (уверенность: {sentiment_score:.2f})\n"
                        if stock_price:
                            message += f"💰 <b>Котировка {company}:</b> {stock_price} RUB\n"

                        print(message)
                        # Отправляем сообщение в Telegram
                        # send_telegram_message(message)
                        # print(f"Отправлено сообщение для {company} в Telegram.")

        # Проверяем новости каждые 10 минут
        time.sleep(300)

if __name__ == "__main__":
    main()
