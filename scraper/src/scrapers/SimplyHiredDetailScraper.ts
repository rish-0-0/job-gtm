import { JobDetailScraper, JobDetails } from "./JobDetailScraper";

export class SimplyHiredDetailScraper extends JobDetailScraper {
    public async scrapeJobDetails(url: string): Promise<JobDetails> {
        const startTime = Date.now();

        try {
            console.log(`[SimplyHiredDetailScraper] Scraping: ${url}`);

            await this.initBrowser();

            const response = await this.page!.goto(url, {
                waitUntil: 'networkidle2',
                timeout: 30000
            });

            if (!response || response.status() !== 200) {
                const error = `Page returned status ${response?.status()}`;
                console.log(`[SimplyHiredDetailScraper] ${error}`);
                return {
                    ...this.createEmptyDetails(url, error),
                    scrapeDurationMs: Date.now() - startTime
                };
            }

            // Wait for content to load
            await new Promise(resolve => setTimeout(resolve, 2000));

            // Get full job description - try multiple selectors
            let jobDescriptionFull = "";
            const descriptionSelectors = [
                '[data-testid="viewJobBodyJobFullDescriptionContent"]',
                '[data-testid="viewJobDescription"]',
                '.viewjob-description',
                '.job-description',
                '#job-description',
                'article'
            ];

            for (const selector of descriptionSelectors) {
                try {
                    const element = await this.page!.$(selector);
                    if (element) {
                        const text = await this.page!.evaluate(
                            (el) => el.textContent || "",
                            element
                        );
                        if (text && text.length > 100) {
                            jobDescriptionFull = text.trim();
                            console.log(`[SimplyHiredDetailScraper] Found description with selector: ${selector} (${text.length} chars)`);
                            break;
                        }
                    }
                } catch {
                    // Continue to next selector
                }
            }

            // Get full page text for AI
            const fullPageText = await this.getFullPageText();

            const duration = Date.now() - startTime;
            console.log(`[SimplyHiredDetailScraper] ✅ Scraped in ${duration}ms - Description: ${jobDescriptionFull.length} chars, Page: ${fullPageText.length} chars`);

            return {
                jobDescriptionFull,
                fullPageText,
                scrapedUrl: url,
                scrapeSuccess: true,
                scrapeError: null,
                scrapeDurationMs: duration
            };

        } catch (error) {
            const errorMsg = error instanceof Error ? error.message : 'Unknown error';
            console.error(`[SimplyHiredDetailScraper] ❌ Error: ${errorMsg}`);
            return {
                ...this.createEmptyDetails(url, errorMsg),
                scrapeDurationMs: Date.now() - startTime
            };
        } finally {
            await this.closeBrowser();
        }
    }
}
