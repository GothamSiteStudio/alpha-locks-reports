"""HTML Report Exporter for Alpha Locks Reports"""
from datetime import date
from typing import List, Optional
from pathlib import Path

from .models import Job, JobResult, Technician
from .calculator import CommissionCalculator
from config import COMPANY_NAME


class HTMLReportExporter:
    """
    Generates HTML reports for technician commissions.
    Styled to match the PDF report format.
    """
    
    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: Arial, sans-serif;
            font-size: 11px;
            background-color: #f5f5f5;
            padding: 20px;
        }}
        
        .report-container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        
        .report-title {{
            text-align: center;
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 20px;
            color: #333;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        
        th {{
            background-color: #d3d3d3;
            color: #333;
            font-weight: bold;
            padding: 10px 8px;
            text-align: center;
            border: 1px solid #999;
            font-size: 12px;
        }}
        
        td {{
            padding: 8px;
            border: 1px solid #ccc;
            vertical-align: middle;
        }}
        
        tr:nth-child(even) {{
            background-color: #fafafa;
        }}
        
        tr:hover {{
            background-color: #f0f0f0;
        }}
        
        .col-date {{
            text-align: center;
            width: 80px;
        }}
        
        .col-address {{
            text-align: left;
            min-width: 200px;
        }}
        
        .col-percent {{
            text-align: center;
            width: 50px;
        }}
        
        .col-money {{
            text-align: right;
            width: 80px;
        }}
        
        .summary-row {{
            background-color: #00ffff !important;
            font-weight: bold;
        }}
        
        .summary-row td {{
            border: 1px solid #999;
        }}
        
        .negative {{
            color: #c00;
        }}
        
        .positive {{
            color: #060;
        }}
        
        @media print {{
            body {{
                background-color: white;
                padding: 0;
            }}
            
            .report-container {{
                box-shadow: none;
                padding: 10px;
            }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="report-title">{title}</div>
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Address</th>
                    <th>%</th>
                    <th>Total</th>
                    <th>Parts</th>
                    <th>Cash</th>
                    <th>CC</th>
                    <th>Check</th>
                    <th>FEE</th>
                    <th>Tech Profit</th>
                    <th>Balance</th>
                </tr>
            </thead>
            <tbody>
{rows}
            </tbody>
        </table>
    </div>
</body>
</html>"""

    ROW_TEMPLATE = """                <tr>
                    <td class="col-date">{date}</td>
                    <td class="col-address">{address}</td>
                    <td class="col-percent">{percent}</td>
                    <td class="col-money">{total}</td>
                    <td class="col-money">{parts}</td>
                    <td class="col-money">{cash}</td>
                    <td class="col-money">{cc}</td>
                    <td class="col-money">{check}</td>
                    <td class="col-money">{fee}</td>
                    <td class="col-money">{tech_profit}</td>
                    <td class="col-money {balance_class}">{balance}</td>
                </tr>"""

    SUMMARY_ROW_TEMPLATE = """                <tr class="summary-row">
                    <td class="col-date">{job_count}</td>
                    <td class="col-address"></td>
                    <td class="col-percent"></td>
                    <td class="col-money">{total}</td>
                    <td class="col-money">{parts}</td>
                    <td class="col-money">{cash}</td>
                    <td class="col-money">{cc}</td>
                    <td class="col-money">{check}</td>
                    <td class="col-money">{fee}</td>
                    <td class="col-money">{tech_profit}</td>
                    <td class="col-money {balance_class}">{balance}</td>
                </tr>"""

    def __init__(self, technician: Technician):
        self.technician = technician
        self.calculator = CommissionCalculator()
        self.results: List[JobResult] = []
    
    def add_jobs(self, jobs: List[Job]) -> None:
        """Add jobs and calculate results."""
        self.results.extend(self.calculator.calculate_batch(jobs))
    
    def clear(self) -> None:
        """Clear all results."""
        self.results = []
    
    def get_date_range(self) -> tuple:
        """Get the date range of jobs."""
        dates = [r.job.job_date for r in self.results if r.job.job_date]
        if not dates:
            return None, None
        return min(dates), max(dates)
    
    def _format_money(self, value: float, show_zero: bool = False) -> str:
        """Format money value."""
        if value == 0 and not show_zero:
            return ""
        if value < 0:
            return f"-${abs(value):,.2f}"
        return f"${value:,.2f}"
    
    def _format_date(self, d: Optional[date]) -> str:
        """Format date as YYYYMMDD."""
        if d is None:
            return ""
        return d.strftime("%Y%m%d")
    
    def generate_html(self) -> str:
        """Generate HTML report."""
        # Build title
        start_date, end_date = self.get_date_range()
        if start_date and end_date:
            date_range = f"{start_date.strftime('%m.%d.%Y')} - {end_date.strftime('%m.%d.%Y')}"
        else:
            date_range = ""
        
        title = f"{COMPANY_NAME} - Technician Report ({self.technician.name})"
        if date_range:
            title += f" {date_range}"
        
        # Build rows
        rows = []
        for r in self.results:
            balance_class = "negative" if r.balance < 0 else ""
            row = self.ROW_TEMPLATE.format(
                date=self._format_date(r.job.job_date),
                address=r.job.address,
                percent=f"{int(r.job.commission_rate * 100)}%",
                total=self._format_money(r.job.total, show_zero=True),
                parts=self._format_money(r.job.parts),
                cash=self._format_money(r.job.cash_amount),
                cc=self._format_money(r.job.cc_amount),
                check=self._format_money(r.job.check_amount),
                fee=self._format_money(r.job.fee),
                tech_profit=self._format_money(r.tech_profit, show_zero=True),
                balance=self._format_money(r.balance, show_zero=True),
                balance_class=balance_class
            )
            rows.append(row)
        
        # Summary row
        summary = self.calculator.calculate_summary(self.results)
        balance_class = "negative" if summary['total_balance'] < 0 else ""
        summary_row = self.SUMMARY_ROW_TEMPLATE.format(
            job_count=f"{summary['job_count']} Jobs",
            total=self._format_money(summary['total_sales'], show_zero=True),
            parts=self._format_money(summary['total_parts']),
            cash=self._format_money(summary['total_cash']),
            cc=self._format_money(summary['total_cc']),
            check=self._format_money(summary['total_check']),
            fee=self._format_money(summary['total_fee']),
            tech_profit=self._format_money(summary['total_tech_profit'], show_zero=True),
            balance=self._format_money(summary['total_balance'], show_zero=True),
            balance_class=balance_class
        )
        rows.append(summary_row)
        
        # Build final HTML
        html = self.HTML_TEMPLATE.format(
            title=title,
            rows="\n".join(rows)
        )
        
        return html
    
    def export_html(self, filepath: str) -> None:
        """Export report to HTML file."""
        html = self.generate_html()
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
