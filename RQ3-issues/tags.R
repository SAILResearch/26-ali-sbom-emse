# RQ3: issue-category prevalence and resolution time per category.
# Run build_issue_categories.py first. It deduplicates issues and assigns categories
# (LLM labels for all issues, human labels for the validated sample).
if (!file.exists("issue_categories.csv") && dir.exists("RQ3-issues")) setwd("RQ3-issues")
View <- function(...) invisible(NULL)
library(dplyr)
library(ggplot2)

df <- read.csv("issue_categories.csv", stringsAsFactors = FALSE)
lab <- df %>% filter(category != "")

# Prevalence: share of labelled issues of a format that carry the category
# (an issue can carry several categories, so shares do not sum to 100)
n_issues <- lab %>% group_by(identifier) %>% summarise(total = n_distinct(Issue_URL), .groups = "drop")
categories <- lab %>%
  group_by(category, identifier) %>%
  summarise(n = n_distinct(Issue_URL), .groups = "drop") %>%
  left_join(n_issues, by = "identifier") %>%
  mutate(percentage = n / total * 100)
write.csv(categories, file = "aggregatedCats.csv")

plot <- ggplot(categories, aes(x = reorder(category, percentage), y = percentage)) +
  geom_bar(aes(fill = identifier), position = "dodge", stat = "identity") +
  ylab("% of Issues") +
  xlab("Issue Categories") +
  labs(fill = "Type of Tool") +
  theme(legend.position = c(0.9, 0.2), legend.direction = "vertical") +
  geom_text(size = 2.5, position = position_dodge(1),
            aes(y = percentage + 0.25, fill = identifier,
                label = paste0(round(percentage, digits = 2), "%"), hjust = 0.08, vjust = 0.3)) +
  theme(axis.text.x = element_text(angle = 90, vjust = 0.5, hjust = 1)) +
  scale_fill_manual(values = c("#999999", "#E69F00")) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.12))) +
  coord_flip()
pdf(file = "tags_prevalence.pdf", width = 8, height = 3.5)
print(plot)
dev.off()

# Resolution time of closed issues per category
closed <- lab %>% filter(State == "closed")
t1 <- closed %>%
  group_by(category, identifier) %>%
  summarise(avg_Resolution_Time = mean(resolve_time_sec, na.rm = TRUE), .groups = "drop")
write.csv(t1, file = "aggregatedTagTime.csv")

plot <- ggplot(t1, aes(x = reorder(category, avg_Resolution_Time), y = avg_Resolution_Time)) +
  geom_bar(aes(fill = identifier), position = "dodge", stat = "identity") +
  ylab("Resolution Time (sec)") +
  xlab("Issue Categories") +
  labs(fill = "Type of Tool") +
  theme(legend.position = c(0.92, 0.85), legend.direction = "vertical") +
  theme(axis.text.x = element_text(angle = 90, vjust = 0.5, hjust = 1)) +
  geom_text(size = 2.5, position = position_dodge(1),
            aes(y = avg_Resolution_Time + max(avg_Resolution_Time, na.rm = TRUE) * 0.01,
                label = formatC(avg_Resolution_Time, format = "e", digits = 1), hjust = 0.08, vjust = 0.3)) +
  scale_fill_manual(values = c("#999999", "#E69F00")) +
  coord_flip()
pdf(file = "tag_resolve_time.pdf", width = 9, height = 5)
print(plot)
dev.off()

# Cliff's delta = P(x > y) - P(x < y); |d| < 0.147 negligible, < 0.33 small, < 0.474 medium, else large
cliffs_delta <- function(x, y) {
    # Cliff's delta = P(x > y) - P(x < y); the Mann-Whitney statistic W counts ties as 1/2
    x <- x[!is.na(x)]; y <- y[!is.na(y)]
    2 * unname(wilcox.test(x, y, exact = FALSE)$statistic) / (length(x) * length(y)) - 1
  }
effect_label <- function(d) {
  a <- abs(d)
  ifelse(a < 0.147, "negligible", ifelse(a < 0.33, "small", ifelse(a < 0.474, "medium", "large")))
}

# Mann-Whitney U test per category (CycloneDX vs SPDX), Bonferroni-corrected over all categories
res <- do.call(rbind, lapply(sort(unique(closed$category)), function(cat) {
  a <- closed$resolve_time_sec[closed$category == cat & closed$identifier == "CycloneDX"]
  b <- closed$resolve_time_sec[closed$category == cat & closed$identifier == "SPDX"]
  d <- cliffs_delta(a, b)
  data.frame(Category = cat, n_CycloneDX = length(a), n_SPDX = length(b),
             mean_days_CycloneDX = mean(a) / 86400, mean_days_SPDX = mean(b) / 86400,
             p_value = wilcox.test(a, b, exact = FALSE)$p.value,
             cliffs_delta_cdx_vs_spdx = d, effect_size = effect_label(d))
}))
res$p_bonferroni <- pmin(1, res$p_value * nrow(res))
write.csv(res, file = "cat_diff_by_format.csv", row.names = FALSE)
print(res)
