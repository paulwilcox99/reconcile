from setuptools import setup, find_packages

setup(
    name="dealtracker",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.1",
        "sqlalchemy>=2.0",
        "openai>=1.30",
        "anthropic>=0.25",
        "pdfplumber>=0.10",
        "pillow>=10.0",
        "python-dotenv>=1.0",
        "rich>=13.0",
        "jinja2>=3.1",
        "weasyprint>=60.0",
        "reportlab>=4.0",
        "pydantic>=2.0",
    ],
    entry_points={
        "console_scripts": [
            "dt=dealtracker.cli:cli",
        ],
    },
    python_requires=">=3.11",
)
