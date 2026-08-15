import { test } from '@playwright/test'
import {
  cryptoDataCenterJourney,
  sandboxCandidateJourney,
} from './support/workstationHarness'

test('crypto data center guides acquisition, quality, and exact snapshot verification', async ({
  page,
}) => cryptoDataCenterJourney(page))

test('sandbox candidate exposes exact lineage and keeps owner actions on trusted CLI', async ({
  page,
}) => sandboxCandidateJourney(page))
