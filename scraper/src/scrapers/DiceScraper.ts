import puppeteer, { Browser, Page } from "puppeteer";
import { JobBoardScraper, JobListing } from "./JobBoardScraper";

export class DiceScraper extends JobBoardScraper {
    private browser: Browser | null = null;
    private page: Page | null = null;
    private currentJobElement: any = null;

    public async scrape(page: number): Promise<JobListing[]> {
        const jobs: JobListing[] = [];

        try {
            console.log(`[DiceScraper] Starting scrape for page ${page}`);

            this.browser = await puppeteer.launch({
                headless: true,
                args: ['--no-sandbox', '--disable-setuid-sandbox']
            });

            this.page = await this.browser.newPage();

            // Set user agent to avoid detection
            await this.page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36');
            await this.page.setViewport({ width: 1920, height: 1080 });

            console.log(`[DiceScraper] Navigating to Dice.com page ${page}...`);
            const response = await this.page.goto(`https://www.dice.com/jobs?radiusUnit=mi&page=${page}`, {
                waitUntil: 'networkidle2',
                timeout: 30000
            });

            // Check if page loaded successfully
            if (!response || response.status() !== 200) {
                console.log(`[DiceScraper] Page ${page} returned status ${response?.status()}. Page may not exist. Returning empty results.`);
                return jobs;
            }

            console.log(`[DiceScraper] Page ${page} loaded successfully, waiting for job cards...`);

            // Wait a bit for dynamic content
            await new Promise(resolve => setTimeout(resolve, 3000));

            // Wait for job cards - they are divs with specific classes
            try {
                await this.page.waitForSelector('[data-testid="job-search-job-card-link"]', { timeout: 10000 });
                console.log(`[DiceScraper] Page ${page} - Found job card elements`);
            } catch (error) {
                console.log(`[DiceScraper] No job cards found on page ${page}. Page may not exist or has no results. Returning empty results.`);
                return jobs;
            }

            // Get all job card containers (parent divs that contain all the job info)
            const jobCards = await this.page.$$('div.flex.flex-col.gap-6.overflow-hidden.rounded-lg.border.bg-surface-primary');
            console.log(`[DiceScraper] Page ${page} - Found ${jobCards.length} job card containers to scrape`);

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
                    console.error(`[DiceScraper] Error scraping individual job card on page ${page}:`, error);
                }
            }

            console.log(`[DiceScraper] Page ${page} - Successfully scraped ${jobs.length} job listings`);
            return jobs;
        } catch (error) {
            console.error(`[DiceScraper] Error during scraping page ${page}:`, error);
            // Return empty array instead of throwing to allow workflow to continue
            return jobs;
        } finally {
            if (this.browser) {
                await this.browser.close();
            }
        }
    }

    protected async getCompanyTitle(): Promise<string> {
        try {
            // Company name is in the link with class containing "line-clamp-2 text-sm"
            const element = await this.currentJobElement.$('span.logo p.line-clamp-2');
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
            // Job title is in the link with data-testid="job-search-job-detail-link"
            const element = await this.currentJobElement.$('[data-testid="job-search-job-detail-link"]');
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
            // Salary is in a div with aria-labelledby="salary-label"
            const element = await this.currentJobElement.$('[aria-labelledby="salary-label"] p');
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
            // Dice doesn't always show experience on the card, look in the description
            const element = await this.currentJobElement.$('[class*="card-description"]');
            if (element) {
                const description = await this.page!.evaluate((el: any) => el.textContent?.trim() || "", element);
                const experienceMatch = description.match(/(\d+\+?\s*(?:to|-)\s*\d+\s*years?|\d+\+?\s*years?)/i);
                return experienceMatch ? experienceMatch[0] : "";
            }
        } catch (error) {
            console.error('Error getting required experience:', error);
        }
        return "";
    }

    protected async getJobLocation(): Promise<string> {
        try {
            // Location is in a p tag with text like "Hybrid in Vienna, Virginia"
            const elements = await this.currentJobElement.$$('p.text-sm.font-normal.text-zinc-600');
            if (elements && elements.length > 0) {
                const locationText = await this.page!.evaluate((el: any) => el.textContent?.trim() || "", elements[0]);
                // First element should be the location
                return locationText;
            }
        } catch (error) {
            console.error('Error getting job location:', error);
        }
        return "";
    }

    protected async getJobDescription(): Promise<string> {
        try {
            // Description is in a p tag with line-clamp-2 class
            const element = await this.currentJobElement.$('p.line-clamp-2.h-10');
            if (element) {
                return await this.page!.evaluate((el: any) => el.textContent?.trim() || "", element);
            }
        } catch (error) {
            console.error('Error getting job description:', error);
        }
        return "";
    }

    protected async getDatePosted(): Promise<string> {
        try {
            // Date is in second p.text-sm.font-normal.text-zinc-600 element (after location)
            const elements = await this.currentJobElement.$$('p.text-sm.font-normal.text-zinc-600');
            if (elements && elements.length > 1) {
                const dateText = await this.page!.evaluate((el: any) => el.textContent?.trim() || "", elements[1]);
                return dateText;
            }
        } catch (error) {
            console.error('Error getting date posted:', error);
        }
        return "";
    }

    protected async getPostingUrl(): Promise<string> {
        try {
            // URL is in the data-testid="job-search-job-detail-link" element
            const element = await this.currentJobElement.$('[data-testid="job-search-job-detail-link"]');
            if (element) {
                const href = await this.page!.evaluate((el: any) => el.getAttribute('href'), element);
                if (href) {
                    return href.startsWith('http') ? href : `https://www.dice.com${href}`;
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
                // Match formats like "$96,900-$141,600 per year" or "$100k-$150k"
                const match = salaryRange.match(/\$?([\d,]+)k?\s*(?:-|to)/i);
                if (match && match[1]) {
                    const value = parseInt(match[1].replace(/,/g, ''));
                    // If it contains 'k', multiply by 1000
                    return salaryRange.toLowerCase().includes('k') && !salaryRange.includes(',') ? value * 1000 : value;
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
                // Match formats like "$96,900-$141,600 per year" or "$100k-$150k"
                const match = salaryRange.match(/(?:-|to)\s*\$?([\d,]+)k?/i);
                if (match && match[1]) {
                    const value = parseInt(match[1].replace(/,/g, ''));
                    // If it contains 'k', multiply by 1000
                    return salaryRange.toLowerCase().includes('k') && !salaryRange.includes(',') ? value * 1000 : value;
                }
            }
        } catch (error) {
            console.error('Error getting max salary:', error);
        }
        return null;
    }

    protected async getSeniorityLevel(): Promise<string> {
        try {
            // Look for seniority level in the job title or description
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
            // Dice doesn't typically show hiring team on the card
            // This would require clicking into the job details
            return "";
        } catch (error) {
            console.error('Error getting hiring team:', error);
        }
        return "";
    }

    protected async getAboutCompany(): Promise<string> {
        try {
            // Company information is typically not available on the card level
            // This would require clicking into the job details
            return "";
        } catch (error) {
            console.error('Error getting about company:', error);
        }
        return "";
    }

    protected async getEmploymentType(): Promise<string> {
        try {
            // Employment type is in a div with aria-labelledby="employmentType-label"
            const element = await this.currentJobElement.$('[aria-labelledby="employmentType-label"] p');
            if (element) {
                return await this.page!.evaluate((el: any) => el.textContent?.trim() || "", element);
            }
        } catch (error) {
            console.error('Error getting employment type:', error);
        }
        return "";
    }
}
