import puppeteer, { Browser, Page } from "puppeteer";
import { JobBoardScraper, JobListing } from "./JobBoardScraper";

export class SimplyHiredScraper extends JobBoardScraper {
    private browser: Browser | null = null;
    private page: Page | null = null;
    private currentJobElement: any = null;

    public async scrape(page: number): Promise<JobListing[]> {
        const jobs: JobListing[] = [];

        try {
            this.browser = await puppeteer.launch({
                headless: true,
                args: ['--no-sandbox', '--disable-setuid-sandbox']
            });

            this.page = await this.browser.newPage();

            // Set user agent to avoid detection
            await this.page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36');
            await this.page.setViewport({ width: 1920, height: 1080 });

            console.log(`Navigating to SimplyHired page 1...`);
            const url = `https://www.simplyhired.co.in/search?l=bangalore%2C%20karnataka`;
            await this.page.goto(url, {
                waitUntil: 'networkidle2',
                timeout: 30000
            });

            console.log('Page loaded, waiting for job cards...');

            // Wait a bit for dynamic content
            await new Promise(resolve => setTimeout(resolve, 3000));

            // Wait for job cards
            await this.page.waitForSelector('[data-testid="searchSerpJob"]', { timeout: 10000 });
            console.log('Found job cards!');

            // If page > 1, navigate to the requested page by clicking pagination
            if (page > 1) {
                console.log(`Navigating to page ${page}...`);
                const paginationSelector = `[data-testid="paginationBlock${page}"]`;

                try {
                    await this.page.waitForSelector(paginationSelector, { timeout: 5000 });
                    await this.page.click(paginationSelector);

                    // Wait for navigation
                    await this.page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 30000 });

                    // Wait for new job cards to load
                    await new Promise(resolve => setTimeout(resolve, 3000));
                    await this.page.waitForSelector('[data-testid="searchSerpJob"]', { timeout: 10000 });

                    console.log(`Successfully navigated to page ${page}`);
                } catch (error) {
                    console.error(`Error navigating to page ${page}:`, error);
                    throw new Error(`Could not navigate to page ${page}. Page may not exist.`);
                }
            }

            // Get all job card containers
            const jobCards = await this.page.$$('[data-testid="searchSerpJob"]');
            console.log(`Found ${jobCards.length} job cards`);

            for (const jobCard of jobCards) {
                this.currentJobElement = jobCard;

                try {
                    const jobListing: JobListing = {
                        companyTitle: await this.getCompanyTitle(),
                        jobRole: await this.getJobRole(),
                        salaryRange: await this.getSalaryRange(),
                        minSalary: await this.getMinSalary(),
                        maxSalary: await this.getMaxSalary(),
                        requiredExperience: await this.getRequiredExperience(),
                        jobLocation: await this.getJobLocation(),
                        jobDescription: await this.getJobDescription(),
                        datePosted: await this.getDatePosted(),
                        postingUrl: await this.getPostingUrl(),
                        seniorityLevel: await this.getSeniorityLevel(),
                        hiringTeam: await this.getHiringTeam(),
                        aboutCompany: await this.getAboutCompany(),
                        employmentType: await this.getEmploymentType()
                    };

                    jobs.push(jobListing);
                } catch (error) {
                    console.error('Error scraping job card:', error);
                }
            }

            return jobs;
        } catch (error) {
            console.error('Error during scraping:', error);
            throw error;
        } finally {
            if (this.browser) {
                await this.browser.close();
            }
        }
    }

    protected async getCompanyTitle(): Promise<string> {
        try {
            const element = await this.currentJobElement.$('[data-testid="companyName"]');
            if (element) {
                return await this.page!.evaluate((el: any) => el.textContent?.trim() || "", element);
            }
        } catch (error) {
            console.error('Error getting company title:', error);
        }
        return "";
    }

    protected async getJobRole(): Promise<string> {
        try {
            // Job title is in the h2 with data-testid="searchSerpJobTitle"
            const element = await this.currentJobElement.$('[data-testid="searchSerpJobTitle"] a');
            if (element) {
                return await this.page!.evaluate((el: any) => el.textContent?.trim() || "", element);
            }
        } catch (error) {
            console.error('Error getting job role:', error);
        }
        return "";
    }

    protected async getSalaryRange(): Promise<string> {
        try {
            const element = await this.currentJobElement.$('[data-testid="searchSerpJobSalaryConfirmed"]');
            if (element) {
                return await this.page!.evaluate((el: any) => el.textContent?.trim() || "", element);
            }
        } catch (error) {
            console.error('Error getting salary range:', error);
        }
        return "";
    }

    protected async getRequiredExperience(): Promise<string> {
        try {
            // Look for experience in requirement chips
            const chips = await this.currentJobElement.$$('[data-testid^="requirementChip"]');
            for (const chip of chips) {
                const text = await this.page!.evaluate((el: any) => el.textContent?.trim() || "", chip);
                const experienceMatch = text.match(/(\d+\+?\s*(?:to|-)\s*\d+\s*years?|\d+\+?\s*years?)/i);
                if (experienceMatch) {
                    return experienceMatch[0];
                }
            }
        } catch (error) {
            console.error('Error getting required experience:', error);
        }
        return "";
    }

    protected async getJobLocation(): Promise<string> {
        try {
            const element = await this.currentJobElement.$('[data-testid="searchSerpJobLocation"]');
            if (element) {
                return await this.page!.evaluate((el: any) => el.textContent?.trim() || "", element);
            }
        } catch (error) {
            console.error('Error getting job location:', error);
        }
        return "";
    }

    protected async getJobDescription(): Promise<string> {
        try {
            // Collect requirement chips as description
            const chips = await this.currentJobElement.$$('[data-testid^="requirementChip"]');
            const requirements: string[] = [];
            for (const chip of chips) {
                const text = await this.page!.evaluate((el: any) => el.textContent?.trim() || "", chip);
                if (text) {
                    requirements.push(text);
                }
            }
            return requirements.join(', ');
        } catch (error) {
            console.error('Error getting job description:', error);
        }
        return "";
    }

    protected async getDatePosted(): Promise<string> {
        try {
            const element = await this.currentJobElement.$('[data-testid="searchSerpJobDateStamp"]');
            if (element) {
                return await this.page!.evaluate((el: any) => el.textContent?.trim() || "", element);
            }
        } catch (error) {
            console.error('Error getting date posted:', error);
        }
        return "";
    }

    protected async getPostingUrl(): Promise<string> {
        try {
            const element = await this.currentJobElement.$('[data-testid="searchSerpJobTitle"] a');
            if (element) {
                const href = await this.page!.evaluate((el: any) => el.getAttribute('href'), element);
                if (href) {
                    return href.startsWith('http') ? href : `https://www.simplyhired.co.in${href}`;
                }
            }
        } catch (error) {
            console.error('Error getting posting URL:', error);
        }
        return "";
    }

    protected async getMinSalary(): Promise<number | null> {
        try {
            const salaryRange = await this.getSalaryRange();
            if (salaryRange) {
                // Handle Indian currency format: "₹20,000 - ₹25,000 a month"
                const match = salaryRange.match(/₹?([\d,]+)\s*(?:-|to)/i);
                if (match && match[1]) {
                    const value = parseInt(match[1].replace(/,/g, ''));
                    return value;
                }
            }
        } catch (error) {
            console.error('Error getting min salary:', error);
        }
        return null;
    }

    protected async getMaxSalary(): Promise<number | null> {
        try {
            const salaryRange = await this.getSalaryRange();
            if (salaryRange) {
                // Handle Indian currency format: "₹20,000 - ₹25,000 a month"
                const match = salaryRange.match(/(?:-|to)\s*₹?([\d,]+)/i);
                if (match && match[1]) {
                    const value = parseInt(match[1].replace(/,/g, ''));
                    return value;
                }
            }
        } catch (error) {
            console.error('Error getting max salary:', error);
        }
        return null;
    }

    protected async getSeniorityLevel(): Promise<string> {
        try {
            const jobRole = await this.getJobRole();
            const description = await this.getJobDescription();
            const combinedText = `${jobRole} ${description}`.toLowerCase();

            if (combinedText.includes('senior') || combinedText.includes('sr.')) return "Senior";
            if (combinedText.includes('lead')) return "Lead";
            if (combinedText.includes('principal')) return "Principal";
            if (combinedText.includes('staff')) return "Staff";
            if (combinedText.includes('junior') || combinedText.includes('jr.')) return "Junior";
            if (combinedText.includes('entry')) return "Entry Level";
            if (combinedText.includes('mid')) return "Mid Level";
        } catch (error) {
            console.error('Error getting seniority level:', error);
        }
        return "";
    }

    protected async getHiringTeam(): Promise<string> {
        try {
            // SimplyHired doesn't show hiring team on card level
            return "";
        } catch (error) {
            console.error('Error getting hiring team:', error);
        }
        return "";
    }

    protected async getAboutCompany(): Promise<string> {
        try {
            // Company information not available on card level
            return "";
        } catch (error) {
            console.error('Error getting about company:', error);
        }
        return "";
    }

    protected async getEmploymentType(): Promise<string> {
        try {
            const element = await this.currentJobElement.$('[data-testid="jobTypeChip-0"]');
            if (element) {
                return await this.page!.evaluate((el: any) => el.textContent?.trim() || "", element);
            }
        } catch (error) {
            console.error('Error getting employment type:', error);
        }
        return "";
    }
}
