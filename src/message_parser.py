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
    TOTAL_CASH_PATTERN = re.compile(r'total\s*cash\s*:?\s*\$?(\d+(?:\.\d{2})?)\$?', re.IGNORECASE)
    TOTAL_CHECK_PATTERN = re.compile(r'total\s*check\s*:?\s*\$?(\d+(?:\.\d{2})?)\$?', re.IGNORECASE)
    TOTAL_CC_PATTERN = re.compile(r'total\s*(?:cc|credit|card)\s*:?\s*\$?(\d+(?:\.\d{2})?)\$?', re.IGNORECASE)
    
    # Pattern for "XXX$ in cash" or "$XXX in cash" or "XXX in cash"
    PRICE_IN_CASH_PATTERN = re.compile(r'\$?(\d+(?:\.\d{2})?)\$?\s*(?:in\s*)?cash', re.IGNORECASE)
    PRICE_IN_CHECK_PATTERN = re.compile(r'\$?(\d+(?:\.\d{2})?)\$?\s*(?:in\s*)?check', re.IGNORECASE)
    PRICE_IN_CC_PATTERN = re.compile(r'\$?(\d+(?:\.\d{2})?)\$?\s*(?:in\s*)?(?:cc|credit|card)', re.IGNORECASE)
    
    # Pattern for "$325 parts $10" (price with parts on same line)
    PRICE_WITH_PARTS_PATTERN = re.compile(r'\$(\d+(?:\.\d{2})?)\s*parts?\s*\$?(\d+(?:\.\d{2})?)', re.IGNORECASE)
    
    # Standalone price ($446 or 446$) - more flexible
    STANDALONE_PRICE_PATTERN = re.compile(r'^\s*\$(\d+(?:\.\d{2})?)\s*$|^\s*(\d+(?:\.\d{2})?)\$\s*$', re.MULTILINE)
    
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
        
        # Find description (lines between address and phone/alpha job)
        description = self._extract_description(text, address, phone)
        
        return ParsedJob(
            address=address,
            total=total,
            parts=parts,
            payment_method=payment_method,
            description=description,
            phone=phone
        )
    
    def parse_multiple_jobs(self, text: str) -> List[ParsedJob]:
        """
        Parse multiple job messages from a single text block.
        Jobs are separated by "alpha job" markers.
        
        Args:
            text: Text containing multiple job messages
            
        Returns:
            List of ParsedJob objects
        """
        jobs = []
        
        # Split by "alpha job" marker
        parts = re.split(r'(alpha\s*job)', text, flags=re.IGNORECASE)
        
        # Reconstruct job blocks (each job ends with "alpha job")
        job_blocks = []
        current_block = ""
        
        for i, part in enumerate(parts):
            if re.match(r'alpha\s*job', part, re.IGNORECASE):
                # This is the marker, add it to current block and save
                current_block += part
                # Look for pricing info after the marker
                if i + 1 < len(parts):
                    # Get the next part and extract only the pricing info
                    next_part = parts[i + 1]
                    pricing_lines = []
                    for line in next_part.split('\n'):
                        line_stripped = line.strip()
                        # Check if this line contains pricing info
                        if (self.TOTAL_CASH_PATTERN.search(line) or
                            self.TOTAL_CHECK_PATTERN.search(line) or
                            self.TOTAL_CC_PATTERN.search(line) or
                            self.STANDALONE_PRICE_PATTERN.search(line) or
                            self.PARTS_PATTERN.search(line) or
                            line_stripped == ''):
                            pricing_lines.append(line)
                        else:
                            # This is the start of a new job
                            break
                    
                    current_block += '\n'.join(pricing_lines)
                    # Update the next part to remove the pricing info we used
                    remaining_lines = next_part.split('\n')[len(pricing_lines):]
                    parts[i + 1] = '\n'.join(remaining_lines)
                
                job_blocks.append(current_block)
                current_block = ""
            else:
                current_block += part
        
        # Don't forget the last block if it doesn't end with alpha job
        if current_block.strip():
            job_blocks.append(current_block)
        
        # Parse each job block
        for block in job_blocks:
            if block.strip():
                job = self.parse_single_job(block)
                if job:
                    jobs.append(job)
        
        return jobs
    
    def _extract_address(self, text: str, lines: List[str]) -> Optional[str]:
        """Extract address from text."""
        # First check for labeled format (Addr: or Address:)
        match = self.ADDR_LABEL_PATTERN.search(text)
        if match:
            return match.group(1).strip()
        
        # Then try regex pattern for standard address format
        match = self.ADDRESS_PATTERN.search(text)
        if match:
            return match.group(0).strip()
        
        # Fallback: first line that looks like an address (contains numbers and common street suffixes)
        for line in lines:
            line = line.strip()
            if re.search(r'\d+.*(?:St|Ave|Rd|Blvd|Dr|Ln|Way|Pl|Ct|Broadway)', line, re.IGNORECASE):
                # Could be multi-line address, check next line for city/state
                return line
        
        # Last resort: first non-empty line
        for line in lines:
            if line.strip() and not self.ALPHA_JOB_PATTERN.search(line):
                return line.strip()
        
        return None
    
    def _extract_total(self, text: str) -> Tuple[Optional[float], str]:
        """Extract total amount and payment method."""
        # Check for "Total cash XXX"
        match = self.TOTAL_CASH_PATTERN.search(text)
        if match:
            return float(match.group(1)), 'cash'
        
        # Check for "Total check XXX"
        match = self.TOTAL_CHECK_PATTERN.search(text)
        if match:
            return float(match.group(1)), 'check'
        
        # Check for "Total cc/credit XXX"
        match = self.TOTAL_CC_PATTERN.search(text)
        if match:
            return float(match.group(1)), 'cc'
        
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
