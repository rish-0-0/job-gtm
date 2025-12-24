import puppeteer, { Browser, Page } from "puppeteer";

export interface JobDetails {
    // The main content we need - full job description from the detail page
    jobDescriptionFull: string;

    // Full page text for AI to process and extract everything else
    fullPageText: string;

    // Scrape metadata
    scrapedUrl: string;
    scrapeSuccess: boolean;
    scrapeError: string | null;
    scrapeDurationMs: number;
}

export abstract class JobDetailScraper {
    protected browser: Browser | null = null;
    protected page: Page | null = null;

    /**
     * Scrape the job detail page and return the full content for AI processing
     */
    public abstract scrapeJobDetails(url: string): Promise<JobDetails>;

    protected async initBrowser(): Promise<void> {
        this.browser = await puppeteer.launch({
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
        this.page = await this.browser.newPage();

        await this.page.setUserAgent(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        );
        await this.page.setViewport({ width: 1920, height: 1080 });
    }

    protected async closeBrowser(): Promise<void> {
        if (this.browser) {
            await this.browser.close();
            this.browser = null;
            this.page = null;
        }
    }

    protected createEmptyDetails(url: string, error: string | null = null): JobDetails {
        return {
            jobDescriptionFull: "",
            fullPageText: "",
            scrapedUrl: url,
            scrapeSuccess: false,
            scrapeError: error,
            scrapeDurationMs: 0
        };
    }

    /**
     * Get the full text content of the page body
     */
    protected async getFullPageText(): Promise<string> {
        if (!this.page) return "";
        try {
            const text = await this.page.evaluate(() => document.body.innerText || "");
            return text.substring(0, 100000); // Limit to 100k chars
        } catch (error) {
            console.error('Error getting full page text:', error);
            return "";
        }
    }
}
