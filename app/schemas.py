from enum import Enum
from fastapi import Form

class VisaCategory(str, Enum):
    EB1 = "EB1"
    EB2_NIW = "EB2_NIW"

class EB1Evidence(str, Enum):
    AWARDS = "A. Evidence of receipt of lesser nationally or internationally recognized prizes or awards for excellence"
    MEMBERSHIPS = "B. Evidence of membership in associations in the field which demand outstanding achievement"
    PUBLICATIONS = "C. Evidence of published material about the applicant"
    JUDGING = "D. Evidence that the applicant has been asked to judge the work of others"
    CONTRIBUTIONS = "E. Evidence of the applicant's original scientific, scholarly contributions"
    AUTHORSHIP = "F. Evidence of the applicant's authorship of scholarly articles"
    EXHIBITIONS = "G. Evidence that the applicant's work has been displayed at artistic exhibitions"
    LEADERSHIP = "H. Evidence of the applicant's performance of a leading or critical role"
    SALARY = "I. Evidence that the applicant commands a high salary"
    COMMERCIAL = "J. Evidence of the applicant's commercial successes"
    SUPPORT_LETTERS = "Letters of Support"
    PROFESSIONAL_PLAN = "Professional Plan"

class EB2Evidence(str, Enum):
    GENERAL_DOCUMENTS = "01_General_Documents"
    APPLICANT_BACKGROUND = "02_Applicant_Background"
    CRITERION_1 = "03_NIW_Criterion_1_Significant_Merit_and_Importance"
    CRITERION_2 = "04_NIW_Criterion_2_Positioned_to_Advance_the_Field"
    CRITERION_3 = "05_NIW_Criterion_3_Benefit_to_USA_Without_Labor_Certification"
    RECOMMENDATION_LETTERS = "06_Letters_of_Recommendation"
    PEER_REVIEWED = "07_Peer_Reviewed_Publications"
    ADDITIONAL = "08_Additional_Supporting_Documents"

class EB2SubFolders(str, Enum):
    # General Documents
    COVER_LETTER = "01.1_Petitioner_Cover_Letter"
    I140_FORM = "01.2_I-140_Form"
    FEE_PAYMENT = "01.3_Fee_Payment_Receipt"
    CHECKLIST = "01.4_Checklist_of_Evidence"
    
    # Applicant Background
    RESUME = "02.1_Resume_CV"
    DIPLOMAS = "02.2_Diplomas_Transcripts"
    CERTIFICATIONS = "02.3_Professional_Certifications"
    EVALUATION = "02.4_Academic_Evaluation"
    EMPLOYMENT = "02.5_Employment_History"