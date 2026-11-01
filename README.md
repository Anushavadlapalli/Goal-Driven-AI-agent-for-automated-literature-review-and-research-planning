# Goal Driven AI Agent for Automated Literature Review and Research Planning

An AI-assisted research application that searches academic papers, helps analyze literature, supports research planning, and generates PDF reports.

## Features
- User registration and login
- Research paper search using Semantic Scholar and arXiv
- AI-assisted literature analysis using Groq (Llama 3.3 70B Versatile)
- Papers-by-year information
- PDF report generation
- Research summary audio-script generation

## Tech Stack
- Backend: Python, Flask
- Frontend: HTML, CSS, JavaScript
- Research sources: Semantic Scholar, arXiv
- LLM API: Groq
- PDF generation: ReportLab

## Project Structure
```text
backend/
  app.py
  requirements.txt
  .env.example
frontend/
  templates/
  static/
.gitignore
```

## Setup
1. Install Python 3.10+.
2. Open a terminal in the `backend` directory.
3. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Set environment variables. Copy `.env.example` to `.env` and add your own Groq API key and a strong Flask secret key. Never commit `.env`.
6. Start the application:
   ```bash
   python app.py
   ```
7. Open `http://127.0.0.1:5000` in your browser.

## Security
Do not commit API keys, passwords, or real `.env` files. Use environment variables for secrets.

## Author
Anusha Vadlapalli
