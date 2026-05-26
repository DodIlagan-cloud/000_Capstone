"""PDF processing and text extraction service."""

import re
from typing import List, Dict, Tuple
from datetime import datetime
import logging
from pypdf import PdfReader
import io

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Service for processing PDF documents and extracting text and transactions."""
    
    def __init__(self):
        self.logger = logger
    
    def extract_text_from_pdf(self, file_content: bytes) -> Tuple[str, int]:
        """
        Extract text content from a PDF file.
        
        Args:
            file_content: Binary content of the PDF file
            
        Returns:
            Tuple of (extracted_text, page_count)
        """
        try:
            pdf_file = io.BytesIO(file_content)
            reader = PdfReader(pdf_file)
            
            extracted_text = ""
            for page in reader.pages:
                extracted_text += page.extract_text() + "\n"
            
            return extracted_text, len(reader.pages)
        except Exception as e:
            self.logger.error(f"Error extracting text from PDF: {e}")
            raise
    
    def extract_transactions(self, text: str) -> List[Dict]:
        """
        Extract transaction data from extracted text.
        
        This is a basic implementation that looks for common patterns.
        You can enhance this based on your specific PDF formats.
        
        Args:
            text: Extracted text from PDF
            
        Returns:
            List of transaction dictionaries
        """
        transactions = []
        
        # Pattern for date - trying to match common formats
        # YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, etc.
        date_pattern = r'(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})'
        
        # Pattern for amounts - looking for currency amounts
        amount_pattern = r'([+-]?\s*\$?\s*\d+[.,]\d{2})'
        
        # Split text into lines and process
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try to extract date and amount
            date_match = re.search(date_pattern, line)
            amount_matches = re.findall(amount_pattern, line)
            
            if date_match and amount_matches:
                try:
                    date_str = date_match.group(1)
                    # Normalize date format
                    transaction_date = self._parse_date(date_str)
                    
                    for amount_str in amount_matches:
                        amount = self._parse_amount(amount_str)
                        
                        transaction = {
                            "date": transaction_date,
                            "description": line[:50],  # Use first 50 chars as description
                            "amount": amount,
                            "transaction_type": "credit" if amount >= 0 else "debit",
                            "reference": None
                        }
                        transactions.append(transaction)
                except Exception as e:
                    self.logger.debug(f"Could not parse transaction from line '{line}': {e}")
                    continue
        
        return transactions
    
    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        """
        Parse a date string in various formats.
        
        Args:
            date_str: Date string to parse
            
        Returns:
            datetime object
        """
        # Remove whitespace
        date_str = date_str.strip()
        
        # Try different formats
        formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%m-%d-%Y",
            "%Y/%m/%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d/%m/%y",
            "%m/%d/%y",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # If no format matched, return today's date
        return datetime.now()
    
    @staticmethod
    def _parse_amount(amount_str: str) -> float:
        """
        Parse an amount string and convert to float.
        
        Args:
            amount_str: Amount string to parse
            
        Returns:
            Float amount
        """
        # Remove whitespace and currency symbols
        amount_str = amount_str.strip().replace('$', '').replace(',', '.').strip()
        
        try:
            # Handle multiple dots/commas (European vs US format)
            if amount_str.count('.') > 1 or amount_str.count(',') > 1:
                # Likely European format with thousand separators
                amount_str = amount_str.replace('.', '').replace(',', '.')
            
            return float(amount_str)
        except ValueError:
            return 0.0
    
    def detect_document_type(self, text: str) -> str:
        """
        Detect the type of PDF document based on its content.
        
        Args:
            text: Extracted text from PDF
            
        Returns:
            Document type string
        """
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['bank', 'account', 'statement', 'balance']):
            return "bank_statement"
        elif any(word in text_lower for word in ['invoice', 'bill', 'payment', 'total due']):
            return "invoice"
        elif any(word in text_lower for word in ['receipt', 'purchase', 'item']):
            return "receipt"
        else:
            return "unknown"
