import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Import data from CSV export
df = pd.read_csv('survey_data_10_cases.csv')

# Clean column names for easier access (example)
df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
print(df.info())  # Inspect data types and non-null counts
print(df.head())   # View first rows of the dataframe



# Select columns related to tool adoption (example)
tool_columns = ['intelligent_document_processing', 'predictive_analytics', 'rpa', 'gen_ai_drafting']
adoption_counts = df[tool_columns].applymap(lambda x: 1 if x in ['Using occasionally', 'Using regularly'] else 0).sum()

# Create figure
plt.figure(figsize=(10, 6))
adoption_counts.sort_values().plot(kind='barh', color='steelblue')
plt.title('Figure 4.1: Adoption Frequency of AI/ Automation Tools (n=10)')
plt.xlabel('Number of Firms Reporting Use')
plt.tight_layout()
plt.savefig('fig4_1_adoption_frequency.png', dpi=300)  # Save for thesis inclusion
plt.show()