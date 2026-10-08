from pipeline import run_pipeline


result = run_pipeline("sample_pdfs/020_pika_modul2_DGpraktik.pdf")

print("\nPriority:", result.priority)
print("Score:", result.score)

print("\nFindings:")

for finding in result.findings:
    print("\n---")
    print("Type:", finding.type)
    print("Severity:", finding.severity)
    print("Title:", finding.title)
    print("Evidence:", finding.evidence)
    print("Reason:", finding.reason)