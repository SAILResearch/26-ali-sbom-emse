setwd('/Users/abdulalib/Desktop/Postdoc/Academic/SBOMsWork/DataCollectionNew')

# Assuming you have already loaded your dataframe into R, let's call it df

# Load necessary libraries
library(ggplot2)
df = read.csv('top250_stats.csv')
View(df)

# Convert 'date' column to proper date format
df$date <- as.Date(df$creation_date)
df$duration <- as.numeric(df$date - min(df$date))


# Initialize variables
p_value <- Inf
num_rows <- NULL

while (p_value <= 0.05 || is.infinite(p_value)) {
  # Calculate the number of rows to select for each type
  num_rows <- min(sum(df$type == "SPDX"), sum(df$type == "CycloneDX"))
  
  # Select an equal number of rows for each type
  selected_SPDX <- df %>%
    filter(type == "SPDX") %>%
    slice_sample(.,n=200)
  
  selected_CycloneDX <- df %>%
    filter(type == "CycloneDX") %>%
    slice_sample(.,n=200)
  
  # Combine the selected rows into one dataframe
  selected_df <- rbind(selected_SPDX, selected_CycloneDX)
  
  # Perform Wilcoxon test
  wilcoxon_result <- wilcox.test(duration ~ type, data = selected_df,p.adjust.method = "bonferroni")
  
  # Update p-value
  p_value <- wilcoxon_result$p.value
  print(p_value)
}

wilcox.test(duration ~ type, data = selected_df,p.adjust.method = "bonferroni")
golden <- selected_df

summary(merged_df[merged_df$type == "SPDX",]$duration)
summary(merged_df[merged_df$type == "CycloneDX",]$duration)

# Calculate the duration since the earliest date for each type
df$duration <- as.numeric(df$date - min(df$date))

# Plotting
plot <- ggplot(df, aes(x = duration)) +
  geom_histogram(binwidth = 50, aes(fill = type), alpha = 0.85) +
  labs(x = "Duration (days)",
       y = "Number of Projects",
       fill = "Type") +
  theme(legend.position = c(0.4, 0.95), legend.direction = "horizontal") 

pdf(file = "top250_creationtrend.pdf",width = 4, height = 3)
plot
dev.off()
