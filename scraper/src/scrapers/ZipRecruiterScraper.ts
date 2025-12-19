import puppeteer, { Browser, Page } from "puppeteer";
import { JobBoardScraper, JobListing } from "./JobBoardScraper";

export class ZipRecruiterScraper extends JobBoardScraper {
    private browser: Browser | null = null;
    private page: Page | null = null;
    private currentJobElement: any = null;

    public async scrape(page: number): Promise<JobListing[]> {
        const jobs: JobListing[] = [];

        try {
            console.log(`[ZipRecruiterScraper] Starting scrape for page ${page}`);

            this.browser = await puppeteer.launch({
                headless: true,
                args: ['--no-sandbox', '--disable-setuid-sandbox']
            });

            this.page = await this.browser.newPage();

            // Set user agent to avoid detection
            await this.page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36');
            await this.page.setViewport({ width: 1920, height: 1080 });

            console.log(`[ZipRecruiterScraper] Navigating to ZipRecruiter page ${page}...`);
            const url = `https://www.ziprecruiter.in/jobs/search?d=&l=&lat=&long=&page=${page}&q=&remote=on_site&sort=published_at`;
            const response = await this.page.goto(url, {
                waitUntil: 'networkidle2',
                timeout: 30000
            });

            // Check if page loaded successfully
            if (!response || response.status() !== 200) {
                console.log(`[ZipRecruiterScraper] Page ${page} returned status ${response?.status()}. Page may not exist. Returning empty results.`);
                return jobs;
            }

            console.log(`[ZipRecruiterScraper] Page ${page} loaded successfully, waiting for job cards...`);

            // Wait a bit for dynamic content
            await new Promise(resolve => setTimeout(resolve, 3000));

            // Wait for job listings
            try {
                await this.page.waitForSelector('li.job-listing', { timeout: 10000 });
                console.log(`[ZipRecruiterScraper] Page ${page} - Found job listing elements`);
            } catch (error) {
                console.log(`[ZipRecruiterScraper] No job listings found on page ${page}. Page may not exist or has no results. Returning empty results.`);
                return jobs;
            }

            // Get all job listing containers
            const jobCards = await this.page.$$('li.job-listing');
            console.log(`[ZipRecruiterScraper] Page ${page} - Found ${jobCards.length} job listings to scrape`);

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
                    console.error(`[ZipRecruiterScraper] Error scraping individual job card on page ${page}:`, error);
                }
            }

            console.log(`[ZipRecruiterScraper] Page ${page} - Successfully scraped ${jobs.length} job listings`);
            return jobs;
        } catch (error) {
            console.error(`[ZipRecruiterScraper] Error during scraping page ${page}:`, error);
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
            // Company name is in ul.jobList-introMeta li with fa-building icon
            const element = await this.currentJobElement.$('ul.jobList-introMeta li:has(i.fa-building)');
            if (element) {
                const text = await this.page!.evaluate((el: any) => el.textContent?.trim() || "", element);
                // Remove the icon text if present
                return text.replace(/^\s*\S+\s*/, '').trim();
            }
        } catch (error) {
            console.error('[ZipRecruiterScraper] Error getting company title:', error);
        }
        return "";
    }

    protected async getJobRole(): Promise<string> {
        try {
            // Job title is in a.jobList-title strong tag
            const element = await this.currentJobElement.$('a.jobList-title strong');
            if (element) {
                return await this.page!.evaluate((el: any) => el.textContent?.trim() || "", element);
            }
        } catch (error) {
            console.error('[ZipRecruiterScraper] Error getting job role:', error);
        }
        return "";
    }

    protected async getSalaryRange(): Promise<string> {
        try {
            // ZipRecruiter doesn't always show salary on listing cards
            // Look for any salary information in the description or metadata
            return "";
        } catch (error) {
            console.error('[ZipRecruiterScraper] Error getting salary range:', error);
        }
        return "";
    }

    protected async getRequiredExperience(): Promise<string> {
        try {
            // Look for experience in the job description
            const description = await this.getJobDescription();
            const experienceMatch = description.match(/(\d+\+?\s*(?:to|-)\s*\d+\s*years?|\d+\+?\s*years?)/i);
            return experienceMatch ? experienceMatch[0] : "";
        } catch (error) {
            console.error('[ZipRecruiterScraper] Error getting required experience:', error);
        }
        return "";
    }

    protected async getJobLocation(): Promise<string> {
        try {
            // Location is in ul.jobList-introMeta li with fa-map-marker-alt icon
            const element = await this.currentJobElement.$('ul.jobList-introMeta li:has(i.fa-map-marker-alt)');
            if (element) {
                const text = await this.page!.evaluate((el: any) => el.textContent?.trim() || "", element);
                // Remove the icon text if present
                return text.replace(/^\s*\S+\s*/, '').trim();
            }
        } catch (error) {
            console.error('[ZipRecruiterScraper] Error getting job location:', error);
        }
        return "";
    }

    protected async getJobDescription(): Promise<string> {
        try {
            // Description is in div.jobList-description
            const element = await this.currentJobElement.$('div.jobList-description');
            if (element) {
                return await this.page!.evaluate((el: any) => el.textContent?.trim() || "", element);
            }
        } catch (error) {
            console.error('[ZipRecruiterScraper] Error getting job description:', error);
        }
        return "";
    }

    protected async getDatePosted(): Promise<string> {
        try {
            // Date is in div.jobList-date
            const element = await this.currentJobElement.$('div.jobList-date');
            if (element) {
                return await this.page!.evaluate((el: any) => el.textContent?.trim() || "", element);
            }
        } catch (error) {
            console.error('[ZipRecruiterScraper] Error getting date posted:', error);
        }
        return "";
    }

    protected async getPostingUrl(): Promise<string> {
        try {
            // URL is in a.jobList-title element
            const element = await this.currentJobElement.$('a.jobList-title');
            if (element) {
                const href = await this.page!.evaluate((el: any) => el.getAttribute('href'), element);
                if (href) {
                    return href.startsWith('http') ? href : `https://www.ziprecruiter.in${href}`;
                }
            }
        } catch (error) {
            console.error('[ZipRecruiterScraper] Error getting posting URL:', error);
        }
        return "";
    }

    protected async getMinSalary(): Promise<number | null> {
        try {
            const salaryRange = await this.getSalaryRange();
            if (salaryRange) {
                const match = salaryRange.match(/₹?([\d,]+)k?\s*(?:-|to)/i);
                if (match && match[1]) {
                    const value = parseInt(match[1].replace(/,/g, ''));
                    return salaryRange.toLowerCase().includes('k') && !salaryRange.includes(',') ? value * 1000 : value;
                }
            }
        } catch (error) {
            console.error('[ZipRecruiterScraper] Error getting min salary:', error);
        }
        return null;
    }

    protected async getMaxSalary(): Promise<number | null> {
        try {
            const salaryRange = await this.getSalaryRange();
            if (salaryRange) {
                const match = salaryRange.match(/(?:-|to)\s*₹?([\d,]+)k?/i);
                if (match && match[1]) {
                    const value = parseInt(match[1].replace(/,/g, ''));
                    return salaryRange.toLowerCase().includes('k') && !salaryRange.includes(',') ? value * 1000 : value;
                }
            }
        } catch (error) {
            console.error('[ZipRecruiterScraper] Error getting max salary:', error);
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
            console.error('[ZipRecruiterScraper] Error getting seniority level:', error);
        }
        return "";
    }

    protected async getHiringTeam(): Promise<string> {
        try {
            // ZipRecruiter doesn't show hiring team on card level
            return "";
        } catch (error) {
            console.error('[ZipRecruiterScraper] Error getting hiring team:', error);
        }
        return "";
    }

    protected async getAboutCompany(): Promise<string> {
        try {
            // Company information not available on card level
            return "";
        } catch (error) {
            console.error('[ZipRecruiterScraper] Error getting about company:', error);
        }
        return "";
    }

    protected async getEmploymentType(): Promise<string> {
        try {
            // Look for employment type keywords in description
            const description = await this.getJobDescription();
            const descLower = description.toLowerCase();

            if (descLower.includes('full-time') || descLower.includes('full time')) return "Full-time";
            if (descLower.includes('part-time') || descLower.includes('part time')) return "Part-time";
            if (descLower.includes('contract')) return "Contract";
            if (descLower.includes('temporary')) return "Temporary";
            if (descLower.includes('internship')) return "Internship";
        } catch (error) {
            console.error('[ZipRecruiterScraper] Error getting employment type:', error);
        }
        return "";
    }
}
