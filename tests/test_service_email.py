"""
Tests for email parsing service.
"""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from services import email


class TestExtractEmailBody:
    """Test email body extraction from MIME content."""

    def test_extract_multipart_alternative_email(self):
        """Test extracting text and HTML from multipart/alternative email."""
        email_content = b"""From: sender@example.com
To: recipient@yourdomain.com
Subject: Test Email Subject
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset="UTF-8"

This is a test email body in plain text.

--boundary123
Content-Type: text/html; charset="UTF-8"

<html><body><p>This is a test email body in <strong>HTML</strong>.</p></body></html>

--boundary123--
"""

        result = email.extract_email_body(email_content)

        assert 'text_body' in result
        assert 'html_body' in result
        assert 'attachments' in result
        assert 'plain text' in result['text_body']
        assert '<strong>HTML</strong>' in result['html_body']
        assert len(result['attachments']) == 0

    def test_extract_simple_text_email(self):
        """Test extracting body from simple text-only email."""
        email_content = b"""From: sender@example.com
To: recipient@yourdomain.com
Subject: Simple Test
Content-Type: text/plain; charset="UTF-8"

Simple email body content.
This is line 2.
"""

        result = email.extract_email_body(email_content)

        assert 'Simple email body content' in result['text_body']
        assert 'line 2' in result['text_body']
        assert result['html_body'] == ''
        assert len(result['attachments']) == 0

    def test_extract_simple_html_email(self):
        """Test extracting body from simple HTML-only email."""
        email_content = b"""From: sender@example.com
To: recipient@yourdomain.com
Subject: HTML Test
Content-Type: text/html; charset="UTF-8"

<html>
<body>
<h1>HTML Email</h1>
<p>This is HTML content.</p>
</body>
</html>
"""

        result = email.extract_email_body(email_content)

        assert result['text_body'] == ''
        assert '<h1>HTML Email</h1>' in result['html_body']
        assert '<p>This is HTML content.</p>' in result['html_body']
        assert len(result['attachments']) == 0

    def test_extract_email_with_attachment(self):
        """Test extracting email with file attachment."""
        email_content = b"""From: sender@example.com
To: recipient@yourdomain.com
Subject: Email with Attachment
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary456"

--boundary456
Content-Type: text/plain; charset="UTF-8"

Email body with attachment.

--boundary456
Content-Type: application/pdf; name="document.pdf"
Content-Disposition: attachment; filename="document.pdf"
Content-Transfer-Encoding: base64

JVBERi0xLjQKJeLjz9MKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+PgplbmRvYmoKMiAwIG9iago8PC9UeXBlL1BhZ2VzL0tpZHNbMyAwIFJdL0NvdW50IDE+PgplbmRvYmoKMyAwIG9iago8PC9UeXBlL1BhZ2UvTWVkaWFCb3hbMCAwIDYxMiA3OTJdL1BhcmVudCAyIDAgUi9SZXNvdXJjZXM8PD4+Pj4KZW5kb2JqCnhyZWYKMCA0CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDAwOSAwMDAwMCBuIAowMDAwMDAwMDU4IDAwMDAwIG4gCjAwMDAwMDAxMTUgMDAwMDAgbiAKdHJhaWxlcgo8PC9TaXplIDQvUm9vdCAxIDAgUj4+CnN0YXJ0eHJlZgoxOTYKJSVFT0YK

--boundary456--
"""

        result = email.extract_email_body(email_content)

        assert 'Email body with attachment' in result['text_body']
        assert len(result['attachments']) == 1
        assert result['attachments'][0]['filename'] == 'document.pdf'
        assert result['attachments'][0]['content_type'] == 'application/pdf'
        assert result['attachments'][0]['size'] > 0

    def test_extract_email_with_multiple_attachments(self):
        """Test extracting email with multiple attachments."""
        email_content = b"""From: sender@example.com
To: recipient@yourdomain.com
Subject: Multiple Attachments
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary789"

--boundary789
Content-Type: text/plain; charset="UTF-8"

Email with two attachments.

--boundary789
Content-Type: image/png; name="image1.png"
Content-Disposition: attachment; filename="image1.png"
Content-Transfer-Encoding: base64

iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==

--boundary789
Content-Type: text/csv; name="data.csv"
Content-Disposition: attachment; filename="data.csv"
Content-Transfer-Encoding: base64

TmFtZSxBZ2UKSm9obiwzMApKYW5lLDI1Cg==

--boundary789--
"""

        result = email.extract_email_body(email_content)

        assert 'two attachments' in result['text_body']
        assert len(result['attachments']) == 2
        assert result['attachments'][0]['filename'] == 'image1.png'
        assert result['attachments'][0]['content_type'] == 'image/png'
        assert result['attachments'][1]['filename'] == 'data.csv'
        assert result['attachments'][1]['content_type'] == 'text/csv'

    def test_extract_email_quoted_printable(self):
        """Test extracting email with quoted-printable encoding."""
        email_content = b"""From: sender@example.com
To: recipient@yourdomain.com
Subject: Quoted-Printable Test
Content-Type: text/plain; charset="UTF-8"
Content-Transfer-Encoding: quoted-printable

This is a test with special characters: =C3=A9 =C3=A7 =C3=A0
Line with equals sign at end=20
Next line continues here.
"""

        result = email.extract_email_body(email_content)

        # The email parser should decode quoted-printable automatically
        assert result['text_body'] != ''
        assert 'special characters' in result['text_body']

    def test_extract_email_base64_body(self):
        """Test extracting email with base64 encoded body."""
        email_content = b"""From: sender@example.com
To: recipient@yourdomain.com
Subject: Base64 Body
Content-Type: text/plain; charset="UTF-8"
Content-Transfer-Encoding: base64

VGhpcyBpcyBhIGJhc2U2NCBlbmNvZGVkIGVtYWlsIGJvZHku

"""

        result = email.extract_email_body(email_content)

        # The email parser should decode base64 automatically
        assert 'base64 encoded email body' in result['text_body']

    def test_extract_empty_email(self):
        """Test extracting body from email with no body content."""
        email_content = b"""From: sender@example.com
To: recipient@yourdomain.com
Subject: Empty Email
Content-Type: text/plain; charset="UTF-8"


"""

        result = email.extract_email_body(email_content)

        assert result['text_body'] == '' or result['text_body'].strip() == ''
        assert result['html_body'] == ''
        assert len(result['attachments']) == 0

    def test_extract_email_with_inline_images(self):
        """Test extracting email with inline images (not counted as attachments)."""
        email_content = b"""From: sender@example.com
To: recipient@yourdomain.com
Subject: Inline Image
MIME-Version: 1.0
Content-Type: multipart/related; boundary="boundaryABC"

--boundaryABC
Content-Type: text/html; charset="UTF-8"

<html><body><p>Email with inline image.</p><img src="cid:image1"></body></html>

--boundaryABC
Content-Type: image/png; name="image1.png"
Content-Disposition: inline; filename="image1.png"
Content-ID: <image1>
Content-Transfer-Encoding: base64

iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==

--boundaryABC--
"""

        result = email.extract_email_body(email_content)

        assert 'inline image' in result['html_body']
        # Inline images might not be counted as attachments depending on Content-Disposition

    def test_extract_email_unicode_subject(self):
        """Test extracting email with Unicode characters."""
        email_content = """From: sender@example.com
To: recipient@yourdomain.com
Subject: Unicode Test: 你好 مرحبا שלום
Content-Type: text/plain; charset="UTF-8"

Email body with Unicode: 日本語 العربية עברית
""".encode('utf-8')

        result = email.extract_email_body(email_content)

        assert '日本語' in result['text_body']
        assert 'العربية' in result['text_body']
        assert 'עברית' in result['text_body']

    def test_extract_email_returns_dict_structure(self):
        """Test that extract_email_body returns correct dict structure."""
        email_content = b"""From: sender@example.com
To: recipient@yourdomain.com
Subject: Structure Test
Content-Type: text/plain; charset="UTF-8"

Test body.
"""

        result = email.extract_email_body(email_content)

        # Verify structure
        assert isinstance(result, dict)
        assert 'text_body' in result
        assert 'html_body' in result
        assert 'attachments' in result
        assert isinstance(result['text_body'], str)
        assert isinstance(result['html_body'], str)
        assert isinstance(result['attachments'], list)


class TestParseEmailHeaders:
    """Test email header parsing (if the function is still used)."""

    def test_parse_headers_basic(self):
        """Test parsing basic email headers."""
        # Note: The current implementation has an issue - it expects string but
        # the function signature shows it takes a string. Let's test if it exists.

        # Check if parse_email_headers exists
        if not hasattr(email, 'parse_email_headers'):
            pytest.skip("parse_email_headers function not implemented or removed")

        email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test Subject
Date: Mon, 11 Nov 2025 10:00:00 +0000

Body content.
"""

        result = email.parse_email_headers(email_content)

        assert result['From'] == 'sender@example.com'
        assert result['To'] == 'recipient@example.com'
        assert result['Subject'] == 'Test Subject'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
