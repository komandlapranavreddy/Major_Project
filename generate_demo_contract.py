from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import sys

def create_demo_pdf(filename):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # --- Page 1 ---
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, height - 80, "NON-DISCLOSURE AND CONFIDENTIALITY AGREEMENT")
    
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 120, "This Agreement is made by and between the Disclosing Party and the Receiving Party.")
    
    # Clause 1
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, height - 160, "1. Definitions")
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 180, "'Confidential Information' shall mean any data or information that is proprietary to")
    c.drawString(100, height - 195, "the Disclosing Party and not generally known to the public.")

    # Clause 2
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, height - 230, "2. Scope of Agreement")
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 250, "This Agreement applies to all information shared on or after the Effective Date.")

    # Clause 3
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, height - 290, "3. Use of Information")
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 310, "The Receiving Party shall use the Confidential Information solely for the Purpose.")

    # Clause 4 (Our target clause for demo)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, height - 350, "4. Confidentiality Obligations")
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 370, "The Receiving Party shall keep confidential all non-public information disclosed by the Disclosing Party...")
    
    # Clause 5
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, height - 410, "5. Required Disclosures")
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 430, "If compelled by law, the Receiving Party must provide immediate prior notice.")
    
    # Clause 6
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, height - 470, "6. Return of Materials")
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 490, "Upon request, all materials must be returned or destroyed within 10 business days.")

    # Clause 7 (Our second target clause)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, height - 530, "7. Termination")
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 550, "Either party may terminate this Agreement upon 30 days written notice in the event of a material breach...")

    # Clause 8
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, height - 590, "8. No License")
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 610, "No intellectual property rights are granted under this Agreement.")
    
    c.showPage()
    
    # --- Page 2 ---
    # Clauses 9 through 20
    clauses = [
        ("9. Warranty", "The Disclosing Party warrants it has the right to disclose the information."),
        ("10. Limitation of Liability", "Neither party shall be liable for indirect, incidental, or consequential damages."),
        ("11. Equitable Relief", "A breach may cause irreparable harm for which monetary damages are inadequate."),
        ("12. Entire Agreement", "This Agreement constitutes the entire understanding between the parties."),
        ("13. Severability", "If any provision is found invalid, the remaining provisions remain in full effect."),
        ("14. Waiver", "Failure to enforce any right does not constitute a waiver of future enforcement."),
        ("15. Assignment", "Neither party may assign this Agreement without prior written consent."),
        ("16. Notices", "All notices shall be in writing and delivered via certified mail or email."),
        ("17. Governing Law", "This Agreement shall be governed by the laws of the State of Delaware."),
        ("18. Dispute Resolution", "Any disputes shall be resolved through binding arbitration."),
        ("19. Amendments", "Modifications must be made in writing and signed by both parties."),
        ("20. Counterparts", "This Agreement may be executed in counterparts, each deemed an original.")
    ]
    
    y = height - 80
    for title, text in clauses:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, y, title)
        y -= 20
        c.setFont("Helvetica", 12)
        c.drawString(100, y, text)
        y -= 40
        
        # If we get too close to the bottom, create a new page
        if y < 100:
            c.showPage()
            y = height - 80
            
    c.save()

if __name__ == "__main__":
    create_demo_pdf("demo_contract.pdf")
    print("Created demo_contract.pdf successfully!")
