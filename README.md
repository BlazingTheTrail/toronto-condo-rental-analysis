# Toronto Condo Rental Market Web Scraping & Analysis

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Pandas](https://img.shields.io/badge/Pandas-Data%20Analysis-orange)
![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup-Web%20Scraping-green)
![Status](https://img.shields.io/badge/Status-Completed-brightgreen)

## Overview

This project collects Toronto condo rental listing data from Condos.ca and analyzes rental price patterns across areas, property characteristics, furnishing status, parking availability, bathrooms, and unit size.

The goal is to turn raw web listing data into a clean analytical dataset and produce business-oriented insights that can support rental market research, pricing comparison, and neighbourhood-level analysis.

## Business Questions

- Which Toronto areas have the highest number of rental condo listings?
- How does rent vary by area, property type, furnishing status, bathrooms, parking, and unit size?
- Is unit size strongly associated with rental price?
- Which features appear most relevant when comparing condo rental prices?

## Tech Stack

* Python
* Pandas
* Requests
* BeautifulSoup
* Matplotlib
* Seaborn
* Jupyter Notebook

## Project Workflow

```text
Web Scraping
    ↓
Data Cleaning
    ↓
Feature Engineering
    ↓
Exploratory Data Analysis
    ↓
Visualization & Business Insights
```text

## Key Insights

* Downtown Toronto had the highest concentration of condo rental listings.
* Furnished units generally showed higher average rents.
* Parking availability had a measurable impact on rental prices.
* Larger condo units displayed decreasing rent-per-square-foot trends.
* Rental pricing patterns varied significantly across neighbourhoods.

## Future Improvements

* Build machine learning models to predict rental prices.
* Add geospatial analysis using postal codes and mapping APIs.
* Automate data collection pipelines.
* Deploy interactive dashboards using Streamlit or Tableau.
## Project Structure

```text
.
├── README.md
├── requirements.txt
├── .gitignore
├── data/
│   ├── raw/
│   └── processed/
├── notebooks/
│   └── toronto_condo_rental_analysis.ipynb
├── outputs/
│   └── charts/
└── src/
    ├── scraper.py
    ├── cleaning.py
    ├── analysis.py
    └── config.py
```

## Methodology

### 1. Data Collection

The scraper collects listing URLs from Toronto rental search pages and extracts key listing-level attributes, including:

- Address
- Price
- Neighbourhood
- Area
- Bedrooms / rooms
- Bathrooms
- Parking
- Furnishing status
- Building age
- Outdoor space
- Property type
- Unit size

### 2. Data Cleaning

The raw scraped data is cleaned by:

- Removing currency symbols and commas from rent prices
- Converting numeric fields to proper data types
- Parsing unit size ranges into numeric estimates
- Standardizing missing values
- Filtering invalid or incomplete observations
- Removing duplicate listings

### 3. Exploratory Data Analysis

The analysis focuses on:

- Rental price distribution
- Listing count by area
- Listing count by property type
- Furnishing status distribution
- Price vs. size relationship
- Area-level summary statistics

## Key Improvements from the Original Notebook

The original notebook has been refactored into a more professional portfolio-style project:

- Scraping, cleaning, and analysis logic separated into reusable Python modules
- Cleaner notebook focused on storytelling and results
- More robust request handling with timeout, retry-ready structure, and error management
- Improved naming conventions and project organization
- GitHub-friendly README added
- Requirements and `.gitignore` added for reproducibility

## How to Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the scraper:

```bash
python src/scraper.py
```

Run cleaning:

```bash
python src/cleaning.py
```

Open the notebook:

```bash
jupyter notebook notebooks/toronto_condo_rental_analysis.ipynb
```

## Notes

Websites can change their HTML structure over time. If the scraper stops working, inspect the latest page structure and update the CSS selectors in `src/config.py`.

When scraping public websites, always use responsible request rates, avoid excessive traffic, and respect the website's terms of use.

## Future Enhancements

- Add automated tests for cleaning functions
- Add geospatial visualization by neighbourhood
- Build a rent price prediction model
- Add interactive dashboard using Streamlit or Tableau
- Schedule periodic data collection to track rental market changes over time

## Portfolio Summary

Built a Python-based web scraping and exploratory data analysis project to collect and analyze Toronto condo rental listings. The project demonstrates data collection, data cleaning, feature extraction, exploratory analysis, visualization, and business insight generation using real-world housing market data.
