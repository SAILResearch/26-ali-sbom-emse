# load packages
library(dplyr)
library(tidyr)
library(ggplot2)
if (!file.exists("CycloneNSpdxTools.csv") && dir.exists("RQ2-tools")) setwd("RQ2-tools")

df <- read.csv("CycloneNSpdxTools.csv")
df$X <- NULL
#collection date
date1 <- as.POSIXct("2025-05-01", tz = "UTC", format = "%Y-%m-%d")
#repo creation date
date2 <- as.POSIXct(df$CreationDate, tz = "UTC", format = "%Y-%m-%d")
# Calculate the difference in days
df$days <- as.numeric(difftime(date1, date2, units = "days"))
#View(df)

df[, 6:13] <- (df[, 6:13] / df$days)*10000

gathered_df <- gather(df, attribute, count, -Format, -Tool, -Language, -Repo, -CreationDate, -Language, -days)

#View(gathered_df)
gathered_df$Repo <- NULL
gathered_df$Tool <- NULL
gathered_df$Language <- NULL
gathered_df$days <- NULL
gathered_df$CreationDate <- NULL

df <- gathered_df
names(df)[names(df) == "Format"] <- "format"

df <- df %>%
  filter(attribute!="ClosedIssues") %>%
  filter(attribute!="OpenIssues") 

plot <- ggplot(df, aes(x=reorder(attribute, -(as.numeric(count))), y=log((as.numeric(count))), fill=format)) + 
  geom_boxplot() +
  ylab("Log of \n (metric value / age of repository in days)") + xlab("Community Health Metrics") +
  labs(fill = "Format ") +
  theme(legend.position="top") +
  facet_wrap( ~ attribute, scales="free") +
  #  theme(axis.text.y = element_blank()) +
  theme(
    strip.background = element_blank(),
    strip.text.x = element_blank()
  )

pdf(file = "tool_metrics.pdf",width = 4, height = 3.5)
plot
dev.off()

names(df)[names(df) == "format"] <- "identifier"

df <- na.omit(df)
class_spdx <- subset(df, identifier == "SPDX")
class_cdx <- subset(df, identifier == "CycloneDx")
# Perform paired Wilcoxon signed-rank test for each identifier
p_values <- list()
for (id in unique(df$attribute)) {
  cat("attribute:", id, "\n")
  
  # Subset data for the current identifier
  id_data_A <- subset(class_spdx, attribute == id)$count
  id_data_B <- subset(class_cdx, attribute == id)$count
  
  # Perform Wilcoxon signed-rank test
  #print(wilcox.test(id_data_A, id_data_B, paired = FALSE))
  
  mw_test <- wilcox.test(id_data_A, id_data_B, paired = FALSE)
  p_values[[id]] <- mw_test$p.value
  #cat("p-value: ",mw_test$p.value, "\n")
  # Calculate Cliff's delta
  cliffs_delta <- function(x, y) {
    # Cliff's delta = P(x > y) - P(x < y); the Mann-Whitney statistic W counts ties as 1/2
    x <- x[!is.na(x)]; y <- y[!is.na(y)]
    2 * unname(wilcox.test(x, y, exact = FALSE)$statistic) / (length(x) * length(y)) - 1
  }
  
  delta <- cliffs_delta(id_data_A, id_data_B)
  cat("cliff's delta: ", delta, "\n")
  cat("\n")
}

# Convert p_values list to a vector
p_values_vec <- unlist(p_values)

# Adjust p-values using Bonferroni correction
adjusted_p_values <- p.adjust(p_values_vec, method = "bonferroni")

# Print adjusted p-values
for (i in 1:length(adjusted_p_values)) {
  cat("attribute:", names(adjusted_p_values)[i], "\n")
  cat("adjusted p-value: ", adjusted_p_values[i], "\n")
}
df3 <- df %>%
  group_by(identifier, attribute) %>%
  summarise(mean=mean(as.numeric(count)),
            median = median((count)))
View(df3)

