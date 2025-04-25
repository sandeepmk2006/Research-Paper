import sqlite3
import os
from datetime import datetime
import hashlib
from fpdf import FPDF  # For creating sample PDFs

#creating class
class ResearchPaperRepository:
    def __init__(self, db_name='research_papers.db'):
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        self._initialize_database()
#This func is to initialize database
    def _initialize_database(self):
        """Initialize the database with required tables"""
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()
        
        # Create papers table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                authors TEXT NOT NULL,
                abstract TEXT,
                publication_date TEXT,
                category TEXT,
                file_path TEXT UNIQUE,
                file_hash TEXT UNIQUE,
                upload_date TEXT NOT NULL,
                keywords TEXT
            )
        ''')
        
        # Create full-text search virtual table if FTS5 is available
        try:
            self.cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
                    title, authors, abstract, keywords, 
                    content='papers', 
                    content_rowid='id'
                )
            ''')
            
            # Create triggers to keep FTS table in sync
            self.cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS papers_ai AFTER INSERT ON papers
                BEGIN
                    INSERT INTO papers_fts(rowid, title, authors, abstract, keywords)
                    VALUES (new.id, new.title, new.authors, new.abstract, new.keywords);
                END
            ''')
            
            self.cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS papers_ad AFTER DELETE ON papers
                BEGIN
                    DELETE FROM papers_fts WHERE rowid = old.id;
                END
            ''')
            
            self.cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS papers_au AFTER UPDATE ON papers
                BEGIN
                    DELETE FROM papers_fts WHERE rowid = old.id;
                    INSERT INTO papers_fts(rowid, title, authors, abstract, keywords)
                    VALUES (new.id, new.title, new.authors, new.abstract, new.keywords);
                END
            ''')
        except sqlite3.OperationalError as e:
            print(f"Note: FTS5 might not be available. Some search features may be limited. Error: {e}")
        
        self.conn.commit()
#This is to create sample pdf
    def create_sample_pdf(self, filename="sample_paper.pdf"):
        """Create a sample PDF file for testing"""
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Quantam Mechanishm", ln=1, align='C')
        pdf.cell(200, 10, txt="By: John Wings", ln=2, align='C')
        pdf.multi_cell(0, 10, txt="This is a sample research paper about Quantam Mechanish. It demonstrates how to store research papers in a repository system.")
        pdf.output(filename)
        return filename

    def clear_test_data(self):
        """Clear all test data from the database"""
        self.cursor.execute("DELETE FROM papers WHERE title LIKE 'Deep Learning for%'")
        self.conn.commit()
        if os.path.exists("sample_paper.pdf"):
            os.remove("sample_paper.pdf")
        print("Cleared all test data")

    def add_paper(self, title, authors, file_path=None, abstract=None, publication_date=None, 
                 category=None, keywords=None, create_sample_if_missing=False):
        """
        Add a research paper to the repository
        
        Args:
            title (str): Title of the paper
            authors (str): Comma-separated list of authors
            file_path (str, optional): Path to the paper file
            abstract (str, optional): Abstract of the paper
            publication_date (str, optional): Publication date (YYYY-MM-DD)
            category (str, optional): Category of the paper
            keywords (str, optional): Comma-separated keywords
            create_sample_if_missing (bool): Create sample PDF if file doesn't exist
            
        Returns:
            int: ID of the inserted paper
        """
        if file_path:
            if not os.path.exists(file_path):
                if create_sample_if_missing:
                    file_path = self.create_sample_pdf(file_path)
                    print(f"Created sample PDF at: {file_path}")
                else:
                    raise FileNotFoundError(f"File not found: {file_path}. Set create_sample_if_missing=True to auto-create a sample.")
            
            # Calculate file hash to detect duplicates
            file_hash = self._calculate_file_hash(file_path)
            
            # Check if paper with same hash already exists
            self.cursor.execute('SELECT id FROM papers WHERE file_hash = ?', (file_hash,))
            if self.cursor.fetchone():
                print("Note: This paper already exists in the repository (same file content)")
                return None
        else:
            file_path = None
            file_hash = None
            
        # Get current date for upload_date
        upload_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        self.cursor.execute('''
            INSERT INTO papers (
                title, authors, abstract, publication_date, 
                category, file_path, file_hash, upload_date, keywords
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, authors, abstract, publication_date, category, 
              file_path, file_hash, upload_date, keywords))
        
        paper_id = self.cursor.lastrowid
        self.conn.commit()
        return paper_id

    def _calculate_file_hash(self, file_path):
        """Calculate SHA-256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
# This func defines searching for research paper
    def search_papers(self, query=None, category=None, author=None, year=None):
        """
        Search for papers using full-text search
        
        Args:
            query (str, optional): Search query
            category (str, optional): Filter by category
            author (str, optional): Filter by author
            year (str, optional): Filter by publication year
            
        Returns:
            list: List of matching papers (as dictionaries)
        """
        # Base query
        if query:
            try:
                sql = '''
                    SELECT p.id, p.title, p.authors, p.abstract, p.publication_date, 
                           p.category, p.file_path, p.upload_date, p.keywords
                    FROM papers p
                    JOIN papers_fts f ON p.id = f.rowid
                    WHERE papers_fts MATCH ?
                '''
                params = [query]
            except sqlite3.OperationalError:
                # Fallback to simple search if FTS5 not available
                sql = '''
                    SELECT p.id, p.title, p.authors, p.abstract, p.publication_date, 
                           p.category, p.file_path, p.upload_date, p.keywords
                    FROM papers p
                    WHERE (title LIKE ? OR abstract LIKE ? OR authors LIKE ? OR keywords LIKE ?)
                '''
                params = [f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%']
        else:
            sql = '''
                SELECT p.id, p.title, p.authors, p.abstract, p.publication_date, 
                       p.category, p.file_path, p.upload_date, p.keywords
                FROM papers p
                WHERE 1=1
            '''
            params = []
        
        # Add filters
        if category:
            sql += ' AND p.category = ?'
            params.append(category)
        if author:
            sql += ' AND p.authors LIKE ?'
            params.append(f'%{author}%')
        if year:
            sql += ' AND strftime("%Y", p.publication_date) = ?'
            params.append(year)
            
        self.cursor.execute(sql, params)
        columns = [col[0] for col in self.cursor.description]
        results = [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        return results
# this function is used to categrories research_paper
    def get_all_categories(self):
        """Get all distinct categories in the repository"""
        self.cursor.execute('SELECT DISTINCT category FROM papers WHERE category IS NOT NULL')
        return [row[0] for row in self.cursor.fetchall()]

    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()

def main():
    # Example usage
    repo = ResearchPaperRepository()
    
    try:
        # Clear any existing test data
        repo.clear_test_data()
        
        # Add a paper (will create sample PDF if needed)
        try:
            paper_id = repo.add_paper(
                title="Deep Learning for Natural Language Processing",
                authors="John Smith, Jane Doe",
                file_path="sample_paper.pdf",
                abstract="This paper explores deep learning techniques for NLP tasks...",
                publication_date="2023-05-15",
                category="Machine Learning",
                keywords="deep learning, nlp, transformers",
                create_sample_if_missing=True
            )
            if paper_id:
                print(f"Added paper with ID: {paper_id}")
            else:
                print("Paper already exists (not added again)")
        except Exception as e:
            print(f"Error adding paper: {e}")
        
        # Search papers
        print("\nSearching for papers about 'deep learning':")
        results = repo.search_papers("deep learning", category="Machine Learning")
        for paper in results:
            print(f"\nID: {paper['id']}")
            print(f"Title: {paper['title']}")
            print(f"Authors: {paper['authors']}")
            print(f"Abstract: {paper['abstract'][:100]}...")
        
        # Get all categories
        categories = repo.get_all_categories()
        print("\nAvailable categories:", categories)
        
    finally:
        repo.close()

#this is main
if __name__ == "__main__":
    # Check if fpdf is available
    try:
        from fpdf import FPDF
    except ImportError:
        print("\nImportant: To run this demo, please install fpdf first:")
        print("pip install fpdf")
        exit()

    main()