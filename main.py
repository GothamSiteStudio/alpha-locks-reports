"""Main entry point for Alpha Locks Reports"""
import argparse
from pathlib import Path
from datetime import datetime

from src.models import Technician
from src.calculator import CommissionCalculator
from src.report_generator import ReportGenerator
from src.data_loader import DataLoader
from config import DEFAULT_COMMISSION_RATE


def main():
    parser = argparse.ArgumentParser(description='Generate technician commission reports')
    parser.add_argument('input_file', help='Path to input Excel/CSV file with job data')
    parser.add_argument('--technician', '-t', required=True, help='Technician name')
    parser.add_argument('--commission', '-c', type=float, default=None,
                        help=f'Commission rate (e.g., 0.5 for 50%%). Default: {DEFAULT_COMMISSION_RATE}')
    parser.add_argument('--output', '-o', default=None, help='Output file path')
    
    args = parser.parse_args()
    
    # Create technician
    commission_rate = args.commission if args.commission else DEFAULT_COMMISSION_RATE
    technician = Technician(
        id='tech',
        name=args.technician,
        commission_rate=commission_rate
    )
    
    # Load jobs
    input_path = Path(args.input_file)
    if input_path.suffix.lower() == '.csv':
        jobs = DataLoader.load_from_csv(str(input_path), commission_rate)
    else:
        jobs = DataLoader.load_from_excel(str(input_path), commission_rate)
    
    print(f"Loaded {len(jobs)} jobs")
    
    # Generate report
    generator = ReportGenerator(technician)
    generator.add_jobs(jobs)
    
    # Output path
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f"output/reports/{technician.name}_{timestamp}.xlsx"
    
    generator.export_excel(output_path)
    print(f"Report saved to: {output_path}")
    
    # Print summary
    summary = generator.calculator.calculate_summary(generator.results)
    print(f"\n=== Summary ===")
    print(f"Jobs: {summary['job_count']}")
    print(f"Total Sales: ${summary['total_sales']:,.2f}")
    print(f"Total Parts: ${summary['total_parts']:,.2f}")
    print(f"Tech Profit: ${summary['total_tech_profit']:,.2f}")
    print(f"Balance: ${summary['total_balance']:,.2f}")
    if summary['total_balance'] > 0:
        print(f"  → Technician owes company ${summary['total_balance']:,.2f}")
    else:
        print(f"  → Company owes technician ${abs(summary['total_balance']):,.2f}")


if __name__ == '__main__':
    main()
