
library(dplyr)
library(tidyr)
setwd('/Users/abdulalib/Desktop/Postdoc/Academic/SBOMsWork/DataCollectionNew')

df = read.csv("FinalClassification2.csv")

View(df)


df2 <- df %>%
  group_by(Type, Support) %>%
  summarise(n = n()) %>%
  group_by(Type) %>%
  mutate(percentage = n / sum(n) * 100)


plot <- ggplot(df2, aes(x=Support,y=percentage)) +
  geom_bar(aes(fill = Type), position = "dodge", stat="identity") +
  ylab("% Number of Tools") +
  xlab("Support Format") +
  labs(fill="Type of Tool") +
  theme(legend.position = c(0.2, 0.95), legend.direction = "horizontal") +
  geom_text(size=3 ,position = position_dodge(1) , aes(y=percentage+0.25, fill = Type, label=paste0(round(percentage,digits = 2),"%"), hjust=0.5, vjust=0)) +
  theme(axis.text.x = element_text(angle = 90, vjust = 0.5, hjust=1)) +
  scale_fill_manual(values=c("#999999", "#E69F00"))

pdf(file = "spdx_cdx_dual_os_vs_prop.pdf",width = 8, height = 4)
plot
dev.off()

result <- df %>%
  group_by(Support) %>%
  summarise(across(c(BUILD, ANALYZE, EDIT, VIEW, DIFF, IMPORT, TRANSLATE, MERGE, SUPPORT), ~sum(.)))


View(result)

df_long <- result %>%
  gather(Usecase, Value, -Support)

View(df_long)
df_long$Support <- as.character(df_long$Support)


library(ggplot2)

#write.csv(df_long,file = "sumOfTaxonomy3.csv")
# I manually edited to make the logos more meaningful in terms of order
df_long_2 = read.csv("sumOfTaxonomy3.csv")
# Define the desired order for 'Section'
desired_order <- c("Produce", "Consume", "Transform")  # Replace with your desired order
# Reorder the 'Section' variable
df_long_2$Section <- factor(df_long_2$Section, levels = desired_order)

plot <- ggplot(df_long_2, aes(x=reorder(Usecase,order),y=value)) +
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
  theme(legend.position = c(0.21, 0.95), legend.direction = "horizontal") +
  geom_text(size=3 ,position = position_dodge(1) , aes(y=value+0.25, fill = labels, label=paste0(round(value,digits = 2),"%"), hjust=0.5, vjust=0)) +
  theme(axis.text.x = element_text(angle = 90, vjust = 0.5, hjust=1)) +
  scale_fill_manual(values=c("#999999", "#E69F00","#2a05a6"))
plot

pdf(file = "spdx_vs_cdx_ntia.pdf",width = 8, height = 5)
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
  gather(Usecase, Value, -Support)
View(df3)

library(rstatix)
library(coin)
library(corrplot)
df4 <- df3[df3$Value != 0, ]
df4 <- df4[df4$Usecase != 'Type', ]
df4$Value <- NULL
#write.csv(df4,file="preppingForChi.csv")
#df4 <- read.csv("preppingForChi.csv")

contingency_table <- table(df4$Support, df4$Usecase)
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

pdf(file = "cdx_vs_spdx_residuals.pdf",width = 8, height = 3)
cp <- corrplot(chi_square_result$residuals, is.cor = FALSE,tl.col="black")
dev.off()

# Calculating Associations
View(round(chi_square_result$residuals, 3))

# Calculating Contributions
contrib <- 100*chi_square_result$residuals^2/chi_square_result$statistic
corrplot(contrib, is.cor = FALSE)
View(round(contrib, 3))
