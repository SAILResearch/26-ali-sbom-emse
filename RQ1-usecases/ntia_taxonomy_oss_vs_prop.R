
library(dplyr)
library(tidyr)
setwd('/Users/abdulalib/Desktop/Postdoc/Academic/SBOMsWork/DataCollectionNew')

df = read.csv("FinalClassification.csv")

result <- df %>%
  group_by(Opensource) %>%
  summarise(across(c(BUILD, ANALYZE, EDIT, VIEW, DIFF, IMPORT, TRANSLATE, MERGE, SUPPORT), ~sum(.)))


View(result)

df_long <- result %>%
  gather(Usecase, Value, -Opensource)

View(df_long)
df_long$Opensource <- as.character(df_long$Opensource)

library(ggplot2)

#write.csv(df_long,file = "sumOfTaxonomy.csv")
# I manually edited to make the logos more meaningful in terms of order
df_long_2 = read.csv("sumOfTaxonomy2.csv")

# Define the desired order for 'Section'
desired_order <- c("Produce", "Consume", "Transform")  # Replace with your desired order

# Reorder the 'Section' variable
df_long_2$Section <- factor(df_long_2$Section, levels = desired_order)


plot <- ggplot(df_long_2, aes(x=reorder(Subsection,order),y=value)) +
  geom_bar(aes(fill = labels), position = "dodge", stat="identity") +
  facet_grid(. ~ Section,
             scales = "free_x",
             space = "free_x",
             switch = "x") +
  theme(panel.spacing = unit(0, units = "cm"), # removes space between panels
        strip.placement = "outside", # moves the states down
        strip.background = element_rect(fill = "white")) +
  ylab("% Number of Tools") +
  xlab("NTIA Taxonomy Usecases") +
  labs(fill="Type of Tool") +
  theme(legend.position = c(0.48, 0.98), legend.direction = "horizontal") +
  geom_text(size=3 ,position = position_dodge(1) , aes(y=value+0.25, fill = labels, label=paste0(round(value,digits = 2),"%"), hjust=0.5, vjust=0)) +
  theme(axis.text.x = element_text(angle = 90, vjust = 0.5, hjust=1)) +
  scale_fill_manual(values=c("#999999", "#E69F00"))
plot


pdf(file = "NTIA_tool_classification.pdf",width = 8, height = 5)
plot
dev.off()


# ==============================================
# ==============================================
# ==============================================
# ==============================================
# ==============================================
# ==============================================


View(df)
df2<-df
df2$Name<-NULL

df3 <- df2 %>%
  gather(Usecase, Value, -Opensource)
View(df3)

library(rstatix)
library(coin)
df3 %>% wilcox_test(Value ~ Opensource,p.adjust.method = "bonferroni")
df3 %>%  wilcox_effsize(Value ~ Opensource,p.adjust.method = "bonferroni")

# ==============================================
# ==============================================
# ==============================================
# ==============================================
# ==============================================
# ==============================================
library(corrplot)
df4 <- df3[df3$Value != 0, ]
df4$Value <- NULL
#write.csv(df4,file="preppingForChi.csv")
df4 <- read.csv("preppingForChi.csv")

contingency_table <- table(df4$Opensource, df4$Usecase)
View(contingency_table)
chi_square_result <- chisq.test(contingency_table)

chi_square_statistic <- chi_square_result$statistic
# Calculate Cramer's V manually
n <- sum(contingency_table)  # Total number of observations
num_rows <- nrow(contingency_table)
num_cols <- ncol(contingency_table)

# Calculate Cramer's V
cramers_v <- sqrt(chi_square_statistic / (n * min((num_rows - 1), (num_cols - 1))))

# Print Cramer's V
print("This is the Cramer's effect size: ")
print(cramers_v)

library(corrplot)
corplot <- corrplot(chi_square_result$residuals, is.cor = FALSE,tl.col="black")
pdf(file = "open_vs_prop_residuals.pdf",width = 8, height = 3)
corplot
dev.off()

contrib <- 100*chi_square_result$residuals^2/chi_square_result$statistic
View(round(contrib, 3))

corrplot(contrib, is.cor = FALSE)
View(round(chi_square_result$residuals, 3))

