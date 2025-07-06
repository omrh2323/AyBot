# AyBot 🕸️

**AyBot** is a simple and modular asynchronous web crawler written in Python.  
It is designed to collect web pages, extract useful content and store data in a local SQLite or MySQL database.  
This project is part of a personal search engine experiment.

---

## ✨ Features

- Asynchronous crawling with `aiohttp`
- HTML parsing with `BeautifulSoup`
- Basic link extraction and filtering
- Language detection with `langdetect`
- Spam keyword detection
- Robots.txt and sitemap support (basic)
- Dual storage: MySQL for metadata, SQLite for content
- Lightweight and easy to understand structure

---

## 📁 Project Structure

```
AyBot/
├── AyBot.py
├── core/
│   ├── crawler.py
│   ├── parser.py
│   ├── renderer.py
│   └── scheduler.py
├── database/
│   ├── mysql_handler.py
│   └── sqlite_handler.py
├── utils/
│   ├── config.py
│   ├── helpers.py
│   └── logger.py
├── data/
│   └── ayfilter_data.db
```

---

## 🧪 Requirements

Install dependencies:

```bash
pip install aiohttp beautifulsoup4 langdetect mysql-connector-python psutil
```

---

## ▶️ How to Run

```bash
python AyBot.py
```

---

## 📄 License

This project is open-source under the MIT license.

---

## 🤝 Contributing

This is a hobby project.  
If you want to contribute or give feedback, feel free to open issues or pull requests.
