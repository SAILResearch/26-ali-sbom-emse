import pandas as pd
from datetime import datetime

# Read the original CSV file
df = pd.read_csv("SpdxIssues.csv")

# Filter out rows with empty tags
df = df[df['Tags'].str.len() > 2]  # Assuming the minimum length of a non-empty list is 3 (e.g., '[a]')

# Split the 'Tags' column into individual tags
df['Tags'] = df['Tags'].str.strip("[]").str.replace("'", "").str.split(", ")

# Create a new DataFrame to hold the expanded rows
expanded_rows = []

# Iterate over each row in the original DataFrame
for index, row in df.iterrows():
    # Check if the 'Tags' column is not empty
    if row['Tags']:
        # For each tag in the 'Tags' column, create a new row with the same data
        for tag in row['Tags']:
            expanded_row = row.copy()  # Create a copy of the original row

            # Extracting the repository part from the URL
            repository = "/".join(expanded_row['Issue URL'].split("/")[4:6])
            # Constructing the GitHub URL
            expanded_row['Repo'] = "https://github.com/" + repository
            expanded_row['resolve_time_sec'] = 0

            if expanded_row['State'] == 'closed':
                date1 = datetime.strptime(expanded_row['Created At'].rstrip('Z'), "%Y-%m-%dT%H:%M:%S")
                date2 = datetime.strptime(expanded_row['Closed At'].rstrip('Z'), "%Y-%m-%dT%H:%M:%S")
                # Calculate the time difference
                time_diff = date2 - date1
                # Extract time difference in minutes
                expanded_row['resolve_time_sec'] = time_diff.total_seconds()

            expanded_row['Tags'] = tag  # Replace the 'Tags' value with the current tag
            expanded_rows.append(expanded_row)  # Add the expanded row to the list

# Create a new DataFrame from the list of expanded rows
df_expanded = pd.DataFrame(expanded_rows)

# Write the expanded DataFrame to a new CSV file
df_expanded.to_csv("spdx_issues_with_tags.csv", index=False)
