import { JobBoardScraper, JobListing } from "./JobBoardScraper";

export class IndeedScraper extends JobBoardScraper {

    public async scrape(page: number): Promise<JobListing[]> {
        return [];
    }

    protected async getCompanyTitle(): Promise<string> {
        return "";
    }

    protected async getJobRole(): Promise<string> {
        return "";
    }

    protected async getSalaryRange(): Promise<string> {
        return "";
    }

    protected async getRequiredExperience(): Promise<string> {
        return "";
    }

    protected async getJobLocation(): Promise<string> {
        return "";
    }

    protected async getJobDescription(): Promise<string> {
        return "";
    }

    protected async getDatePosted(): Promise<string> {
        return "";
    }

    protected async getPostingUrl(): Promise<string> {
        return "";
    }

    protected async getMinSalary(): Promise<number | null> {
        return null;
    }

    protected async getMaxSalary(): Promise<number | null> {
        return null;
    }

    protected async getSeniorityLevel(): Promise<string> {
        return "";
    }

    protected async getHiringTeam(): Promise<string> {
        return "";
    }

    protected async getAboutCompany(): Promise<string> {
        return "";
    }

    protected async getEmploymentType(): Promise<string> {
        return "";
    }
}