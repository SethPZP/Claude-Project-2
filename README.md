# SEC EDGAR Filings Scraper

Scrapes SEC EDGAR filings by company CIK number, truncates filing data to concise summaries, and saves results organized by company name. Designed for daily use.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

### Basic daily scrape (last 24 hours)

```bash
python edgar_scraper.py --ciks 320193 789019
```

This scrapes Apple (CIK 320193) and Microsoft (CIK 789019) for 10-K, 10-Q, and 8-K filings from the last day.

### Common CIK numbers

| Company   | CIK      |
|-----------|----------|
| Apple     | 320193   |
| Microsoft | 789019   |
| Tesla     | 1318605  |
| Amazon    | 1018724  |
| Google    | 1652044  |
| Meta      | 1326801  |
| NVIDIA    | 1045810  |

### Scrape last 30 days with filing content

```bash
python edgar_scraper.py --ciks 320193 --days 30 --fetch-content --max-length 1000
```

### Only 10-K annual reports, output as CSV

```bash
python edgar_scraper.py --ciks 320193 789019 --forms 10-K --format csv
```

### Set your contact email (SEC requires this)

```bash
python edgar_scraper.py --ciks 320193 --user-agent "MyApp/1.0 (me@example.com)"
```

## Options

| Flag              | Default               | Description                              |
|-------------------|-----------------------|------------------------------------------|
| `--ciks`          | *(required)*          | CIK numbers to scrape                    |
| `--forms`         | `10-K 10-Q 8-K`      | Filing types to include                  |
| `--days`          | `1`                   | Days back to search                      |
| `--fetch-content` | off                   | Also fetch and truncate document content |
| `--max-length`    | `500`                 | Max characters for truncated content     |
| `--output-dir`    | `edgar_data`          | Output directory                         |
| `--format`        | `both`                | Output: `json`, `csv`, or `both`         |
| `--user-agent`    | `EdgarScraper/1.0`    | SEC-required User-Agent header           |

## Output

Results are saved to `edgar_data/` with the current date stamp:

```
edgar_data/
  filings_20260306.json       # All filings
  filings_20260306.csv        # All filings (CSV)
  by_company/
    Apple_Inc_20260306.json   # Per-company files
    Microsoft_Corp_20260306.json
```

## Daily Cron Job

To run daily at 8 AM:

```bash
crontab -e
# Add:
0 8 * * * cd /path/to/project && python edgar_scraper.py --ciks 320193 789019 1318605
```