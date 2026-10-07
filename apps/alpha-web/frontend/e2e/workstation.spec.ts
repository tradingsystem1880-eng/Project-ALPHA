import {
  registerReferenceTests,
  registerLifecycleTests,
  registerWorkstationFeatureTests,
  registerWorkstationTests,
} from './support/workstationHarness'

registerWorkstationTests()
registerWorkstationFeatureTests()
registerReferenceTests()
registerLifecycleTests()
