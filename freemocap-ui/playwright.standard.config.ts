import {defineConfig} from '@playwright/test';
import base from './playwright.config';
export default defineConfig({...base,workers:1,retries:0,testIgnore:['**/ui-refactor-*.spec.ts'],outputDir:'../.test-artifacts/standard-results',reporter:[['list'],['json',{outputFile:'../.test-artifacts/standard-results/results.json'}]]});
