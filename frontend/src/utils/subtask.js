/**
 * 子任务工具函数
 */
import { MAX_SUBTASK_PROMPTS } from './constants.js'

export function createSubtask() {
  return {
    platform: 'instagram',
    account_name: '',
    account_no: '',
    publish_at: null,
    prompts: Array.from({ length: MAX_SUBTASK_PROMPTS }, () => ''),
    photos: [],
    extra: {}
  }
}

export function createTemplateSubtask() {
  return {
    platform: 'instagram',
    account_name: '',
    account_no: '',
    publish_at: null,
    prompts: Array.from({ length: MAX_SUBTASK_PROMPTS }, () => ''),
    extra: {}
  }
}
