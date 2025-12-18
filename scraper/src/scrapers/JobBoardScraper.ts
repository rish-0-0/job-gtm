export interface JobListing {
    companyTitle: string;
    jobRole: string;
    salaryRange: string;
    minSalary: number | null;
    maxSalary: number | null;
    requiredExperience: string;
    jobLocation: string;
    jobDescription: string;
    datePosted: string;
    postingUrl: string;
    seniorityLevel: string;
    hiringTeam: string;
    aboutCompany: string;
    employmentType: string;
}

export abstract class JobBoardScraper {
    public abstract scrape(page: number): Promise<JobListing[]>;

    protected abstract getCompanyTitle(): Promise<string>;
    protected abstract getJobRole(): Promise<string>;
    protected abstract getSalaryRange(): Promise<string>;
    protected abstract getRequiredExperience(): Promise<string>;
    protected abstract getJobLocation(): Promise<string>;
    protected abstract getJobDescription(): Promise<string>;
    protected abstract getDatePosted(): Promise<string>;
    protected abstract getPostingUrl(): Promise<string>;
    protected abstract getMinSalary(): Promise<number | null>;
    protected abstract getMaxSalary(): Promise<number | null>;
    protected abstract getSeniorityLevel(): Promise<string>;
    protected abstract getHiringTeam(): Promise<string>;
    protected abstract getAboutCompany(): Promise<string>;
    protected abstract getEmploymentType(): Promise<string>;
}