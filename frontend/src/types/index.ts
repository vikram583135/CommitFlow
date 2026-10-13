export interface Repository {
  id: string;
  github_repo_id: string;
  full_name: string;
  default_branch: string;
  allowed_paths: string[];
  is_active: boolean;
  last_synced_at?: string;
}

export interface AIProviderConfig {
  id: string;
  provider: 'openai' | 'anthropic' | 'gemini';
  model_name: string;
  masked_api_key?: string;
  is_active: boolean;
}

export interface Automation {
  id: string;
  title: string;
  task_type: 'coding_practice' | 'documentation' | 'unit_tests' | 'learning_notes';
  instructions: string;
  repository: string;
  repository_details?: Repository;
  ai_config?: string;
  ai_config_details?: AIProviderConfig;
  cron_expression: string;
  timezone: string;
  branch_strategy: 'PULL_REQUEST' | 'DIRECT_PUSH';
  require_approval: boolean;
  max_files: number;
  enabled: boolean;
  last_run_at?: string;
  next_run_at?: string;
}

export interface GeneratedFile {
  id: string;
  file_path: string;
  change_type: 'CREATE' | 'MODIFY';
  original_content?: string;
  new_content: string;
  diff_patch?: string;
}

export interface PublishedChange {
  id: string;
  branch_name: string;
  commit_sha: string;
  commit_message: string;
  pull_request_url?: string;
  pull_request_number?: number;
  published_at: string;
}

export interface Execution {
  id: string;
  automation: string;
  automation_title: string;
  repository_name: string;
  status: 'PENDING' | 'RUNNING' | 'AWAITING_APPROVAL' | 'SUCCESS' | 'FAILED' | 'REJECTED';
  scheduled_slot: string;
  attempt_number: number;
  validation_results?: {
    is_valid: boolean;
    errors: string[];
    warnings: string[];
  };
  error_message?: string;
  started_at: string;
  completed_at?: string;
  generated_files: GeneratedFile[];
  published_change?: PublishedChange;
}
