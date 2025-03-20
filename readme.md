# News Aggregator

## Overview
The News Aggregator is a web application designed to collect, filter, and analyze news articles from various sources. Built with Flask, it provides a user-friendly interface to browse recent news, view detailed articles, and explore trending topics through a dashboard. The application is deployed on Render and uses SQLite as its database, with NLTK for natural language processing to identify popular subjects.

## Features
- **News Listing**: Displays a list of the latest news articles with filters for date, subject, and time period (e.g., last week or month).
- **Article Details**: Allows users to view full details of individual news articles.
- **Dashboard**: Presents a ranking of the top 10 trending topics based on article titles, using trigram analysis.
- **Data Scraping**: Includes a scraper to fetch and update news articles from external sources.
- **Responsive Design**: Styled with CSS for a clean and intuitive user experience.

## Technologies
- **Backend**: Flask, Flask-SQLAlchemy
- **Database**: SQLite
- **Natural Language Processing**: NLTK (stopwords, punkt_tab)
- **Deployment**: Render, Gunicorn
- **Frontend**: HTML, CSS
- **Other Libraries**: BeautifulSoup (for scraping), Python standard libraries

## Installation
To run the application locally, follow these steps:

### Prerequisites
- Python 3.11+
- Git
- Virtualenv (recommended)

### Steps
1. **Clone the Repository**
```bash
git clone https://github.com/yourusername/news-aggregator.git
cd news-aggregator
```

2. **Set Up a Virtual Environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```
3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

4. **Download NLTK Data:**
Obs: The app requires NLTK resources included in the nltk_data directory. If running fresh, ensure it’s present or download manually.
```bash
python -c "import nltk; nltk.download('punkt_tab'); nltk.download('stopwords')"
```

5. **Run the Application**
```bash
python run.py 
```
or
```bash
gunicorn app:app
```
## Project Structure
```
news/
├── app/
│   ├── __init__.py       # Flask app setup
│   ├── routes.py         # Application routes with Blueprint
│   ├── repository.py     # Applying filters to search
│   ├── services.py       # NLTK functions
│   ├── models.py         # Database models
│   ├── scraper.py        # News scraping logic
│   ├── templates/        # HTML templates
│   └── static/           # CSS and static files
├── config.py             # Configuration settings
├── nltk_data/            # NLTK resources (punkt_tab, stopwords)
├── run.py                # Local development entry point
├── Procfile              # Render deployment configuration
├── requirements.txt      # Python dependencies
├── instance/             # Contains db archive database
│   ├── noticias.db       # SQLite database
```

## Usage
Home Page: View and filter the latest news articles at /.
Update News: Trigger a refresh of news data at /atualizar.
Article Details: Click "Veja mais" on any news item to visit /noticia/<id>.
Dashboard: Explore trending topics at /dashboard.

## Future Improvements
Enhanced Filters: Add options like "last 24 hours" or source-based filtering.
Export Functionality: Allow users to download the dashboard ranking as a CSV file.
Caching: Implement Flask-Caching to optimize dashboard performance.

## Contributing
Contributions are welcome! Please fork the repository, create a feature branch, and submit a pull request with your changes.

## License
This project is licensed under the MIT License.