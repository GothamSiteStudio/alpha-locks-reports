"""Message parser for extracting job data from text messages"""
import re
from datetime import date
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ParsedJob:
    """Represents a parsed job from a text message"""
    address: str
    total: float
    parts: float
    payment_method: str  # 'cash', 'cc', 'check'
    description: str = ""
    phone: str = ""
    job_date: Optional[date] = None
    technician_name: str = ""  # Auto-detected technician name
    

class MessageParser:
    """
    Parses job closure messages to extract job data.
    
    Message format examples:
    
    27 Deepwood Hill St, Chappaqua, NY 10514
    locks change 
    (847) 444-9779
    alpha job
    $446
    Parts $15
    
    Or:
    Total cash 1231
    Parts 30
    
    Or:
    Total check 850
    Parts 230
    """
    
    # Regex patterns
    PHONE_PATTERN = re.compile(r'[\+]?1?\s*[\(\-]?\d{3}[\)\-\s]*\d{3}[\-\s]*\d{4}')
    
    # Price patterns - various formats (supports "Total cash 510", "Total cash:510$", "Total cash: $510")
    TOTAL_CASH_PATTERN = re.compile(r'total\s*cash\s*:?\s*\$?([\d,]+(?:\.\d{2})?)\$?', re.IGNORECASE)
    TOTAL_CHECK_PATTERN = re.compile(r'total\s*check\s*:?\s*\$?([\d,]+(?:\.\d{2})?)\$?', re.IGNORECASE)
    TOTAL_CC_PATTERN = re.compile(r'total\s*(?:cc|credit|card)\s*:?\s*\$?([\d,]+(?:\.\d{2})?)\$?', re.IGNORECASE)
    
    # Pattern for "run cc XXX$" or "Total cc ... XXX$" (more flexible CC pattern)
    RUN_CC_PATTERN = re.compile(r'(?:run\s*)?cc\s*\$?([\d,]+(?:\.\d{2})?)\$?', re.IGNORECASE)
    
    # Pattern for "XXX$ in cash" or "$XXX in cash" or "XXX in cash"
    PRICE_IN_CASH_PATTERN = re.compile(r'\$?(\d+(?:\.\d{2})?)\$?\s*(?:in\s*)?cash', re.IGNORECASE)
    PRICE_IN_CHECK_PATTERN = re.compile(r'\$?(\d+(?:\.\d{2})?)\$?\s*(?:in\s*)?check', re.IGNORECASE)
    PRICE_IN_CC_PATTERN = re.compile(r'\$?(\d+(?:\.\d{2})?)\$?\s*(?:in\s*)?(?:cc|credit|card)', re.IGNORECASE)
    PRICE_IN_ZELLE_PATTERN = re.compile(r'\$?(\d+(?:\.\d{2})?)\$?\s*(?:in\s*)?zelle', re.IGNORECASE)
    
    # Pattern for "$325 parts $10" (price with parts on same line)
    PRICE_WITH_PARTS_PATTERN = re.compile(r'\$(\d+(?:\.\d{2})?)\s*parts?\s*\$?(\d+(?:\.\d{2})?)', re.IGNORECASE)
    
    # Standalone price ($446 or 446$) - more flexible, also handles just "400$" or "$400" on a line
    STANDALONE_PRICE_PATTERN = re.compile(r'^\s*\$(\d+(?:\.\d{2})?)\s*$|^\s*(\d+(?:\.\d{2})?)\$?\s*$', re.MULTILINE)
    
    # Pattern for "Total XXX Zelle to Name" format
    TOTAL_ZELLE_PATTERN = re.compile(r'total\s*\$?(\d+(?:\.\d{2})?)\$?\s*zelle', re.IGNORECASE)
    
    # Parts pattern - more flexible (parts $10, parts$10, part $10, part$15)
    PARTS_PATTERN = re.compile(r'parts?\s*\$?\s*(\d+(?:\.\d{2})?)', re.IGNORECASE)
    
    # Alpha job marker
    ALPHA_JOB_PATTERN = re.compile(r'alpha\s*job', re.IGNORECASE)
    
    # Labeled format patterns (Addr:, Ph:, Desc:, Occu:, date:)
    ADDR_LABEL_PATTERN = re.compile(r'addr(?:ess)?\s*:\s*(.+)', re.IGNORECASE)
    PHONE_LABEL_PATTERN = re.compile(r'ph(?:one)?\s*:\s*(.+)', re.IGNORECASE)
    DESC_LABEL_PATTERN = re.compile(r'desc(?:ription)?\s*:\s*(.+)', re.IGNORECASE)
    DATE_LABEL_PATTERN = re.compile(r'date\s*:\s*(.+)', re.IGNORECASE)
    
    # US Address pattern (simplified)
    ADDRESS_PATTERN = re.compile(
        r'\d+[A-Za-z]?\s+[\w\s]+(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Pl|Place|Ct|Court|Circle|Cir|Terrace|Ter|Highway|Hwy|Pkwy|Parkway)\.?\s*,?\s*[\w\s]+,?\s*(?:NY|New York|NJ|New Jersey|CT|Connecticut)\s*\d{5}',
        re.IGNORECASE
    )
    
    def parse_single_job(self, text: str) -> Optional[ParsedJob]:
        """
        Parse a single job message.
        
        Args:
            text: The message text containing job closure info
            
        Returns:
            ParsedJob if successful, None if parsing fails
        """
        lines = text.strip().split('\n')
        if not lines:
            return None
        
        # Find address (usually first line or line matching address pattern)
        address = self._extract_address(text, lines)
        if not address:
            return None
        
        # Find total amount and payment method
        total, payment_method = self._extract_total(text)
        if total is None or total == 0:
            return None
        
        # Find parts
        parts = self._extract_parts(text)
        
        # Find phone
        phone = self._extract_phone(text)
        
        # Find job date
        job_date = self._extract_date(text)
        
        # Find description (lines between address and phone/alpha job)
        description = self._extract_description(text, address, phone)
        
        # Find technician name (last non-empty line that's not pricing info)
        technician_name = self._extract_technician_name(text)
        
        return ParsedJob(
            address=address,
            total=total,
            parts=parts,
            payment_method=payment_method,
            description=description,
            phone=phone,
            job_date=job_date,
            technician_name=technician_name
        )
    
    def parse_multiple_jobs(self, text: str) -> List[ParsedJob]:
        """
        Parse multiple job messages from a single text block.
        Jobs are separated by identifying technician names at the end of each job.
        
        Logic:
        - Each job ends with a technician name (1-2 words, letters only)
        - After the technician name, a new job starts
        - New job starts with: address, phone, timestamp, description, etc.
        
        Args:
            text: Text containing multiple job messages
            
        Returns:
            List of ParsedJob objects
        """
        jobs = []
        lines = text.strip().split('\n')
        
        # Words to ignore (not technician names)
        ignore_words = {'alpha', 'job', 'parts', 'part', 'total', 'cash', 'check', 
                        'cc', 'zelle', 'credit', 'card', 'hlo', 'hello', 'hi'}
        
        def is_technician_name(line: str) -> bool:
            """Check if a line is a technician name (1-2 words, only letters)"""
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            
            if not line_stripped:
                return False
            
            # Must not contain numbers
            if re.search(r'\d', line_stripped):
                return False
            
            # Must not contain special characters
            if re.search(r'[\$\+\(\)\[\]\@\#\%\&\*]', line_stripped):
                return False
            
            # Skip Hebrew
            if re.search(r'[\u0590-\u05FF]', line_stripped):
                return False
            
            # Skip "alpha job" pattern
            if re.match(r'^alpha\s*job$', line_lower):
                return False
            
            # Check for 1-2 words, only letters
            words = line_stripped.split()
            if len(words) > 2:
                return False
            
            # All words must be only letters
            if not all(re.match(r'^[a-zA-Z]+$', w) for w in words):
                return False
            
            # Filter out ignored words
            name_words = [w for w in words if w.lower() not in ignore_words]
            return len(name_words) > 0
        
        def is_new_job_start(line: str) -> bool:
            """Check if a line looks like the start of a new job"""
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            
            if not line_stripped:
                return False
            
            # Timestamp pattern [9:38 PM, 1/7/2026] or similar
            if re.match(r'^\[?\d{1,2}:\d{2}', line_stripped):
                return True
            
            # Address pattern (number + street)
            if re.search(r'^\d+[A-Za-z]?\s+[\w\s]+(?:st|street|ave|avenue|rd|road|blvd|dr|drive|ln|lane|way|pl|place|ct|court)', line_lower, re.IGNORECASE):
                return True
            
            # Phone number
            if self.PHONE_PATTERN.match(line_stripped):
                return True
            
            return False
        
        # Split into job blocks
        job_blocks = []
        current_block = []
        found_pricing_in_block = False
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            
            # Check if this line has pricing info
            has_pricing = (self.TOTAL_CASH_PATTERN.search(line) or
                          self.TOTAL_CHECK_PATTERN.search(line) or
                          self.TOTAL_CC_PATTERN.search(line) or
                          self.RUN_CC_PATTERN.search(line) or
                          self.TOTAL_ZELLE_PATTERN.search(line) or
                          self.PRICE_IN_CASH_PATTERN.search(line) or
                          self.PRICE_IN_CHECK_PATTERN.search(line) or
                          self.PRICE_IN_CC_PATTERN.search(line) or
                          self.PRICE_IN_ZELLE_PATTERN.search(line) or
                          self.STANDALONE_PRICE_PATTERN.search(line) or
                          self.PARTS_PATTERN.search(line))
            
            if has_pricing:
                found_pricing_in_block = True
            
            current_block.append(line)
            
            # Check if this line is a technician name (potential end of job)
            # Only consider it as end if we found pricing info in this block
            if found_pricing_in_block and is_technician_name(line):
                # Look ahead to see if next non-empty line is a new job start
                next_line_idx = i + 1
                while next_line_idx < len(lines) and not lines[next_line_idx].strip():
                    next_line_idx += 1
                
                if next_line_idx >= len(lines) or is_new_job_start(lines[next_line_idx]):
                    # This is the end of a job
                    job_blocks.append('\n'.join(current_block))
                    current_block = []
                    found_pricing_in_block = False
        
        # Don't forget the last block
        if current_block:
            job_blocks.append('\n'.join(current_block))
        
        # Parse each job block
        for block in job_blocks:
            if block.strip():
                job = self.parse_single_job(block)
                if job:
                    jobs.append(job)
        
        return jobs
    
    def _clean_address(self, address: str) -> str:
        """Clean address string by removing description parts and timestamp prefixes."""
        if not address:
            return address
        
        # Remove WhatsApp-style timestamp prefixes like "[4:28 PM, 12/30/2025] Oren:"
        timestamp_patterns = [
            r'^\[?\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?,?\s*\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\]\s*[^:]*:\s*',  # Time first
            r'^\[?\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4},?\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\]\s*[^:]*:\s*',  # Date first
        ]
        for pattern in timestamp_patterns:
            address = re.sub(pattern, '', address, flags=re.IGNORECASE)
        address = address.strip()
        
        # Stop at phone number
        phone_match = self.PHONE_PATTERN.search(address)
        if phone_match:
            address = address[:phone_match.start()].strip()
        
        # Heuristic: If we have a zip code, limit to shortly after zip (to include apartment info)
        # But if there are description words, cut before them.
        
        separators = ["Lock change", "Locks change", "House lockout", "Alpha job", "Alpha Job", "Appointment"]
        split_idx = len(address)
        for sep in separators:
            idx = address.lower().find(sep.lower())
            if idx != -1 and idx < split_idx:
                split_idx = idx
        
        if split_idx < len(address):
            address = address[:split_idx].strip()
            
        return address

    def _extract_address(self, text: str, lines: List[str]) -> Optional[str]:
        """Extract address from text."""
        # First check for labeled format (Addr: or Address:)
        match = self.ADDR_LABEL_PATTERN.search(text)
        if match:
            return self._clean_address(match.group(1).strip())
        
        # Check for address in timestamp lines like "[12/7/25, 3:39:38 PM] Oren: 202 Hartman tarrytown Hlo"
        for line in lines:
             # pattern to capture content after timestamp and sender name
             # Matches: [date] Name: Content (approximate timestamp match)
             timestamp_match = re.match(r'^\[?[\d/\-\.:,\s]+(?:PM|AM)?\]\s*[^:]+:\s*(.+)', line, re.IGNORECASE)
             if timestamp_match:
                 content = timestamp_match.group(1).strip()
                 # Check if content starts with number and looks like address
                 if re.match(r'^\d+\s+[A-Za-z]+', content) and len(content) > 10 and not self.PHONE_PATTERN.match(content):
                     return self._clean_address(content)

        # Check for lines starting with date (e.g. 1.1.2025 Address)
        date_start_pattern = re.compile(r'^\d{1,2}[\./\-]\d{1,2}[\./\-]\d{2,4}\s+(.+)')
        for line in lines:
            match = date_start_pattern.match(line.strip())
            if match:
                content = match.group(1).strip()
                # Content should start with number and looks like address
                if re.match(r'^\d+\s+[A-Za-z]+', content) and len(content) > 10 and not self.PHONE_PATTERN.match(content):
                     return self._clean_address(content)

        # Then try regex pattern for standard address format
        match = self.ADDRESS_PATTERN.search(text)
        if match:
             # Standard pattern usually grabs just the address, but good to be safe
            return self._clean_address(match.group(0).strip())


        # Fallback: first line that looks like an address (contains numbers and common street suffixes)
        for line in lines:
            line = line.strip()
            if re.search(r'\d+.*(?:St|Ave|Rd|Blvd|Dr|Ln|Way|Pl|Ct|Broadway)', line, re.IGNORECASE):
                # Could be multi-line address, check next line for city/state
                return self._clean_address(line)
        
        # Try to find a line that starts with a number and looks like an address (number + words)
        for line in lines:
            line = line.strip()
            # Skip timestamp lines like [12/7/25, 3:39:38 PM]
            if re.match(r'^\[?\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}', line):
                continue
            # Match lines starting with street number followed by text (e.g., "202 Hartman tarrytown")
            if re.match(r'^\d+\s+[A-Za-z]+', line) and len(line) > 10:
                # Make sure it's not just a price or phone
                if not self.PHONE_PATTERN.match(line) and not re.match(r'^\d+\s*\$', line):
                    return self._clean_address(line)
        
        # Last resort: first non-empty line that's not a timestamp or alpha job
        for line in lines:
            line_stripped = line.strip()
            if line_stripped and not self.ALPHA_JOB_PATTERN.search(line):
                # Skip timestamp lines
                if re.match(r'^\[?\d{1,2}[:/\-]', line_stripped):
                    continue
                return self._clean_address(line_stripped)
        
        return None
    
    def _extract_total(self, text: str) -> Tuple[Optional[float], str]:
        """Extract total amount and payment method."""
        # Helper to clean price string (remove commas)
        def clean_price(p: str) -> float:
            return float(p.replace(',', ''))
        
        # Check for "Total cash XXX"
        match = self.TOTAL_CASH_PATTERN.search(text)
        if match:
            return clean_price(match.group(1)), 'cash'
        
        # Check for "Total check XXX"
        match = self.TOTAL_CHECK_PATTERN.search(text)
        if match:
            return clean_price(match.group(1)), 'check'
        
        # Check for "Total cc/credit XXX"
        match = self.TOTAL_CC_PATTERN.search(text)
        if match:
            return clean_price(match.group(1)), 'cc'
        
        # Check for "Total XXX Zelle" format
        match = self.TOTAL_ZELLE_PATTERN.search(text)
        if match:
            return float(match.group(1)), 'check'  # Zelle is treated as check
        
        # Check for "$325 parts $10" format (price with parts on same line)
        match = self.PRICE_WITH_PARTS_PATTERN.search(text)
        if match:
            return float(match.group(1)), 'cash'  # Parts will be extracted separately
        
        # Check for "XXX$ in cash" or "XXX in cash" format
        match = self.PRICE_IN_CASH_PATTERN.search(text)
        if match:
            return float(match.group(1)), 'cash'
        
        # Check for "XXX$ in check" format
        match = self.PRICE_IN_CHECK_PATTERN.search(text)
        if match:
            return float(match.group(1)), 'check'
        
        # Check for "XXX$ in cc" format
        match = self.PRICE_IN_CC_PATTERN.search(text)
        if match:
            return float(match.group(1)), 'cc'
        
        # Check for "XXX zelle" or "XXX$ zelle" format (e.g., "850 zelle to oren")
        match = self.PRICE_IN_ZELLE_PATTERN.search(text)
        if match:
            return float(match.group(1)), 'check'  # Zelle is treated as check
        
        # Check for "run cc XXX$" or just "cc XXX$" format (e.g., "Total cc Oren run cc 486.60$")
        match = self.RUN_CC_PATTERN.search(text)
        if match:
            price_str = match.group(1).replace(',', '')
            return float(price_str), 'cc'
        
        # Check for standalone price ($446 or 446$)
        match = self.STANDALONE_PRICE_PATTERN.search(text)
        if match:
            price = match.group(1) or match.group(2)
            return float(price), 'cash'  # Default to cash
        
        return None, 'cash'
    
    def _extract_parts(self, text: str) -> float:
        """Extract parts cost."""
        # First check for "$325 parts $10" format
        match = self.PRICE_WITH_PARTS_PATTERN.search(text)
        if match:
            return float(match.group(2))
        
        # Regular parts pattern
        match = self.PARTS_PATTERN.search(text)
        if match:
            return float(match.group(1))
        return 0.0
    
    def _extract_phone(self, text: str) -> str:
        """Extract phone number."""
        # First check for labeled format (Ph: or Phone:)
        match = self.PHONE_LABEL_PATTERN.search(text)
        if match:
            # Extract phone from the labeled value
            phone_value = match.group(1).strip()
            # Try to find actual phone number in the value
            phone_match = self.PHONE_PATTERN.search(phone_value)
            if phone_match:
                return phone_match.group(0).strip()
            return phone_value
        
        # Standard phone pattern
        match = self.PHONE_PATTERN.search(text)
        if match:
            return match.group(0).strip()
        return ""
    
    def _extract_date(self, text: str) -> Optional[date]:
        """Extract job date from text."""
        # Check for labeled format (date: or Date:)
        match = self.DATE_LABEL_PATTERN.search(text)
        if match:
            date_str = match.group(1).strip()
            # Try various date formats
            # Format: M/D/YY or MM/DD/YY or M/D/YYYY
            date_patterns = [
                (r'^(\d{1,2})/(\d{1,2})/(\d{2})$', '%m/%d/%y'),      # 1/5/26 -> Jan 5, 2026
                (r'^(\d{1,2})/(\d{1,2})/(\d{4})$', '%m/%d/%Y'),      # 1/5/2026
                (r'^(\d{1,2})-(\d{1,2})-(\d{2})$', '%m-%d-%y'),      # 1-5-26
                (r'^(\d{1,2})-(\d{1,2})-(\d{4})$', '%m-%d-%Y'),      # 1-5-2026
                (r'^(\d{1,2})\.(\d{1,2})\.(\d{2})$', '%m.%d.%y'),    # 1.5.26
                (r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$', '%m.%d.%Y'),    # 1.5.2026
            ]
            
            from datetime import datetime
            for pattern, fmt in date_patterns:
                if re.match(pattern, date_str):
                    try:
                        return datetime.strptime(date_str, fmt).date()
                    except ValueError:
                        continue
        
        return None
    
    def _extract_description(self, text: str, address: str, phone: str) -> str:
        """Extract job description (text between address and phone/alpha job)."""
        # First check for labeled format (Desc: or Description:)
        match = self.DESC_LABEL_PATTERN.search(text)
        if match:
            return match.group(1).strip()
        
        lines = text.split('\n')
        description_lines = []
        started = False
        
        for line in lines:
            line_stripped = line.strip()
            
            # Skip empty lines at the start
            if not started and not line_stripped:
                continue
            
            # Start after address line
            if address and address in line:
                started = True
                # Check if there is description on the same line as address
                idx = line.find(address)
                remainder = line[idx + len(address):].strip()
                if remainder:
                    # Clean remainder from potential date or phone
                    # Sometimes date is at start, address in middle, so remainder is clean.
                    # But if phone is there, cut it.
                    phone_match = self.PHONE_PATTERN.search(remainder)
                    if phone_match:
                        remainder = remainder[:phone_match.start()].strip()
                    
                    # Also stop at "Alpha job" if it's there
                    alpha_match = self.ALPHA_JOB_PATTERN.search(remainder)
                    if alpha_match:
                        remainder = remainder[:alpha_match.start()].strip()

                    if remainder:
                        description_lines.append(remainder)
                continue
            
            if started:
                # Stop at phone, alpha job, or price
                if (self.PHONE_PATTERN.search(line) or 
                    self.ALPHA_JOB_PATTERN.search(line) or
                    self.TOTAL_CASH_PATTERN.search(line) or
                    self.TOTAL_CHECK_PATTERN.search(line) or
                    self.STANDALONE_PRICE_PATTERN.search(line) or
                    self.PARTS_PATTERN.search(line)):
                    break
                
                if line_stripped:
                    description_lines.append(line_stripped)
        
        return ' | '.join(description_lines[:3])  # Max 3 lines
    
    def _extract_technician_name(self, text: str) -> str:
        """
        Extract technician name from the message.
        The technician name is always the last word(s) in the message.
        Can be 1 or 2 words (first name or first + last name).
        
        We ignore irrelevant words like "Alpha", "job", etc.
        """
        lines = text.strip().split('\n')
        
        # Words to ignore (not technician names)
        ignore_words = {'alpha', 'job', 'parts', 'part', 'total', 'cash', 'check', 
                        'cc', 'zelle', 'credit', 'card', 'hlo', 'hello', 'hi'}
        
        # Search from the end of the message for the technician name
        potential_name_lines = []
        
        for line in reversed(lines):
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            
            # Skip empty lines
            if not line_stripped:
                continue
            
            # Skip if it contains numbers (addresses, phones, prices, dates)
            if re.search(r'\d', line_stripped):
                continue
            
            # Skip if it contains special characters (prices, etc.)
            if re.search(r'[\$\+\(\)\[\]]', line_stripped):
                continue
            
            # Skip lines with Hebrew characters
            if re.search(r'[\u0590-\u05FF]', line_stripped):
                continue
            
            # Skip ignored words
            if line_lower in ignore_words:
                continue
            
            # Skip "alpha job" pattern
            if re.match(r'^alpha\s*job$', line_lower):
                continue
            
            # Check if this is a valid name (1-2 words, only letters)
            words = line_stripped.split()
            if len(words) <= 2 and all(re.match(r'^[a-zA-Z]+$', w) for w in words):
                # Filter out ignored words from the name
                name_words = [w for w in words if w.lower() not in ignore_words]
                if name_words:
                    # Found the technician name!
                    return ' '.join(w.title() for w in name_words)
            
            # If we hit a line that's clearly not a name, stop searching
            # (addresses, descriptions, etc.)
            if len(words) > 2:
                break
        
        return ""


def parse_messages(text: str) -> List[ParsedJob]:
    """
    Convenience function to parse job messages.
    
    Args:
        text: Text containing one or more job closure messages
        
    Returns:
        List of ParsedJob objects
    """
    parser = MessageParser()
    return parser.parse_multiple_jobs(text)
