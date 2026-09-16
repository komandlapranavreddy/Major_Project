from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def create_playbook_pdf(filename):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawString(100, height - 80, "Universal Hypotheses Playbook")
    
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 120, "This document contains the standard 17 rules used for evaluating contracts.")
    
    hypotheses = [
        ("1. Contains confidentiality clause", "Must explicitly state that non-public information shall be kept confidential."),
        ("2. Terminable for convenience", "Must allow either party to terminate for any reason without a breach."),
        ("3. Governing law is New York", "Must explicitly state governed by the laws of the State of New York."),
        ("4. Contains non-compete clause", "Must restrict a party from competing during or after the agreement."),
        ("5. Contains non-solicitation clause", "Must restrict poaching of employees, customers, or clients."),
        ("6. Limits liability to contract value", "Must cap damages at the total fees paid under the contract."),
        ("7. Contains indemnification clause", "Must require one party to compensate the other for certain damages."),
        ("8. Requires arbitration", "Must mandate binding arbitration for dispute resolution."),
        ("9. Automatically renews", "Must state the contract renews automatically unless notice is given."),
        ("10. Allows assignment without consent", "Must permit a party to assign the contract without the other's permission."),
        ("11. Includes force majeure clause", "Must excuse performance due to unforeseeable circumstances (Acts of God)."),
        ("12. Defines IP ownership", "Must explicitly state who owns newly created intellectual property."),
        ("13. Requires notice for breach", "Must require a specific written notice period to cure a material breach."),
        ("14. Excludes consequential damages", "Must waive indirect, punitive, or consequential damages."),
        ("15. Contains severability clause", "Must state that if one clause is invalid, the rest of the contract survives."),
        ("16. Contains entire agreement clause", "Must state this document supersedes all prior agreements (integration)."),
        ("17. Permits auditing", "Must give one party the right to audit the records of the other party.")
    ]
    
    y = height - 160
    
    for title, desc in hypotheses:
        c.setFont("Helvetica-Bold", 12)
        c.drawString(100, y, title)
        y -= 15
        
        c.setFont("Helvetica", 10)
        c.drawString(100, y, f"Requirement: {desc}")
        y -= 25
        
        # Pagination check
        if y < 80:
            c.showPage()
            y = height - 80
            
    c.save()

if __name__ == "__main__":
    create_playbook_pdf("universal_hypotheses.pdf")
    print("Created universal_hypotheses.pdf successfully!")
