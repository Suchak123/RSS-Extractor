import csv
import os

class CSVHandler:
    @staticmethod
    def read_websites(input_file):
        if not os.path.exists(input_file):
            print(f"Input CSV file not found: {input_file}")
            print(f"Please create '{input_file}' with a 'url' column")
            print(f"Example format:")
            print(f"url")
            print(f"https://example.com")
            return []
        
        websites = []
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get('url', '').strip()
                    if url:
                        websites.append(url)
            
            if not websites:
                print(f"No URLs found in {input_file}")
                return []
            
            print(f"✓ Loaded {len(websites)} websites from {input_file}")
            return websites
            
        except Exception as e:
            print(f"Error reading CSV: {str(e)}")
            return []
    
    # @staticmethod
    # # def write_results(results, output_file):
    # #     try:
    # #         with open(output_file, 'w', newline='', encoding='utf-8') as f:
    # #             writer = csv.DictWriter(f, fieldnames=['website', 'rss'])
    # #             writer.writeheader()
    # #             writer.writerows(results)
    # #         print(f"\nResults saved to {output_file}")
    # #     except Exception as e:
    # #         print(f"Error writing output CSV: {str(e)}")