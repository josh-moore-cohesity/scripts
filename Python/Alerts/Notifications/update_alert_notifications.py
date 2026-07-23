#!/usr/bin/env python
"""Script Overview"""

### import pyhesity wrapper module
from pyhesity import *
from pyhesity import COHESITY_API
from datetime import datetime
import json

# full catalog of alert type ids/names, paired by index (used by -updatetypes to select every alert type)
ALL_ALERT_TYPE_IDS = [9061,9060,9025,9026,9027,9067,9066,1140,9015,9003,9023,9024,1016,1041,1084,11006,10041,6012,6015,9052,19011,19001,1087,1089,1088,19009,19010,1129,1163,20004,20005,20013,6027,1166,1154,21001,1090,1153,8027,10028,10044,1081,6034,6018,10062,1126,1045,9021,1066,1075,1077,1013,1034,1055,1056,9049,9050,9051,9048,10061,10055,10058,11004,6013,9056,9014,9018,9059,9058,8020,9069,8026,9053,6003,1068,1061,1058,1027,1112,1025,1144,1143,2121,1030,1156,1157,1155,10025,10013,8011,8028,13028,1121,1119,1120,16051,6009,70004,70005,70001,70006,70002,70003,10026,6010,6011,1071,1026,2203,15013,13001,9034,9001,13036,1029,1115,1092,1134,1083,1073,1007,1131,8022,9002,9037,1060,1101,13014,13013,13012,1108,6024,8021,9072,12001,12002,9046,1035,9071,20010,10051,10052,14007,14006,14009,14010,14008,10040,13032,13031,13033,1036,1165,1164,1022,1040,6017,11001,6025,1015,10056,9062,6019,6021,9045,6033,6032,6031,1116,20008,6028,60007,1139,1105,1080,8009,8030,8010,9070,19002,6002,19013,1051,1002,1031,1074,13004,1062,13024,1017,1063,10032,12205,12204,12206,12207,12208,12203,1004,12201,12202,12101,9035,60003,60002,60005,60001,60004,60000,19006,19008,19004,10054,10053,10045,20016,1042,1046,1049,1047,1048,1050,1086,13023,13022,13029,8032,1064,1118,10064,10060,10059,10057,10036,6014,1001,20001,20002,13006,13005,15007,15006,15005,15008,6001,15009,15016,15010,15014,15002,15004,15001,15003,1161,1162,1160,10042,1009,8012,8002,6029,1014,20011,10031,1159,1149,1158,22002,22001,13038,1005,60006,1006,1114,1100,9036,1010,13037,2123,13019,1085,19005,13002,13020,19012,13021,1028,1135,13018,1148,1107,1079,8005,6004,1059,10015,10016,10027,9076,9077,9075,9078,9073,9074,9054,10029,10033,10039,9063,10043,11003,6026,10019,10020,10006,9065,9033,9032,13026,13034,13016,13015,1127,10049,1019,1057,10048,10007,10005,10009,10008,10004,10018,10022,10011,10010,10012,10003,10046,10001,10037,10017,10021,10038,10023,10030,10047,1021,1023,1038,1130,1109,8023,9016,9064,9013,9017,9019,9012,9011,9043,1093,1132,1106,1098,1097,1099,1096,1147,1110,1094,1039,6016,9068,20007,20006,1124,1122,1123,10034,10035,8007,1150,1032,1095,1125,1142,1141,15011,1070,8001,8018,8015,8017,8016,18002,18001,18003,8004,1146,1145,1067,1033,1117,1020,1091,1043,10024,10063,13035,1082,1076,8025,6005,2122,14002,14001,14004,14005,14003,13030,13040,1078,20015,15015,1054,13027,19003,19007,15012,2301,8029,13008,13009,1151,1152,8024,13025,6020,1008,1137,1136,1138,1072,1113,1052,20009,1111,11002,1044,1133,20014,1003,1012,1018,1011,1037,11005,1102,6008,6022,6007,1334,8003,10014,8013,8014,8008,8031,8006,19014,20012,9079,9057,1053,1065,9055,9042,9044,9041,9039,9040,9020,6006,9047,13039,1024,13010,13011,13007,1103,1104,13003,8019,10050,6023,20003]

ALL_ALERT_NAMES = ["AVHighRequestQueueSize","AVHighResponseTime","AVServerConnectionFailed","AVServerLicenseError","AVThreatFound","AbacServerCertExpired","AbacServerNotReachable","AbsoluteUITimeoutChanged","AccessToExternalTargetFailed","ActiveDirectoryNotReachable","AdDomainControllersNotReachable","AdPreferredDomainControllerNotReachable","AddNodeFailed","AddNodeSuccess","AddNodesStarted","AdminAccountWillBeForcedToChangePassword","AgentCertIsAboutToExpire","AlgorithmBacklogAlert","AlgorithmFrequentlyTimeOutAlert","ApolloIssuedActionVersionMismatch","AppInstanceHealthy","AppInstanceUnhealthy","AppNetworkMasterUnhealthy","AppNetworkNodeUnhealthy","AppNetworkResourceUnhealthy","AppRollingUpgradeFailure","AppRollingUpgradeSuccess","AppsModeDisabledDueToSubnetClash","AppsModeEnabledDueToSubnetClashResolution","ArchiveJobFailed","ArchiveJobStuck","ArchiveObjectGCFailedAlert","ArchiveValidationFailedAlert","AthenaSubnetFirstIPMatch","AthenaSubnetFirstIPMismatch","AtomNodeMemoryAboveThreshold","AuditLogFailure","AuditServiceInactive","AwsESIndexingErrors","AzureCEHostCachingEnabled","AzureSecretIsAboutToExpire","BMCModuleNotAvailable","BackgroundOperationTargetAlert","BacklogDuringBlackOut","BackupJobPrePostScriptFailure","BaseOSVersionMismatched","BiosAndBmcVersionMismatch","BlobJournalInconsistency","BondModeAutoMigrated","BondSlavesSpeedInconsistent","BondUnhealthy","BondingModeUnexpected","BootDiskHealth","BridgeMigrationFailed","BridgeMigrationRevertFailed","BucketACLUpdated","BucketCreated","BucketDeleted","BucketMetadataModified","CassandraSourceSnapshotDeletionFailed","CertRenewalFailure","CertificateExpired","CertificateIsAboutToExpire","ChunkFileBadState","ChunkFileContainerInconsistency","ChunkFileInconsistency","ChunkFileReplicaBadState","ChunkMigrationVerifyBrickOwnedNDDChunksFailed","ChunkMigrationVerifyChunkInCfmFailed","ClearStaleMountPointsTimeout","ClockSkewBetweenClusterAndDC","CloneBackupCleanupIssues","CloudDataOpFailure","CloudTierWarning","ClusterBringupError","ClusterGatewayUnReachable","ClusterInterfacesInconsistency","ClusterPartitionCreateFailed","ClusterPendingAuditReportUpload","ClusterServiceGflagsFound","ClusterServicesManuallyStarted","ClusterServicesManuallyStopped","ClusterSpaceUsageHigh","ConfigureVipFailed","ConsoleLoggedOut","ConsoleLoginFailure","ConsoleLoginSuccess","ContinuousDataProtectionAlert","ContinuousDataProtectionDisabled","CorruptFileSystemNotIndexed","CorruptMFTError","CpuThrottled","CreateSnapshotFailed","CreateSnapshotStarted","CreateSnapshotSucceeded","DataIngestAnomalyAlert","DataResilienceAtRisk","DataSourceConnectorCertReachingExpiry","DataSourceConnectorCertRenewed","DataSourceConnectorHealthy","DataSourceConnectorPatchFailed","DataSourceConnectorUnhealthy","DataSourceConnectorUpgradeFailed","DeferSchedule","DirectoriesExceededQuota","DirectoryExceededQuotaAlertLimit","DiskAddedToBlacklist","DiskAddedToCluster","DiskAwaitHigh","DiskIdMismatch","DiskIsBad","DiskMarkedForRemoval","DiskMarkedOffline","DiskNeedFirmwareUpgrade","DiskNotHealthy","DiskOkToRemove","DiskRemovalCancelled","DiskRemovalStuck","DiskRemoved","DiskSlotAvailable","DiskSpaceLow","DiskSwapped","DiskWithCorruptedPartitionTable","DiskWithTooManyDeltaRecords","DnsServerConnectionFailed","DnsServerUnReachable","DnsServerUnassigned","DriveFault","DrivePresent","DriveRemoved","DuplicateIpDetected","ECConversionBacklogged","ESDiskUsageExceedsThreshold","EnableObjectServicesViewAllowlistFeature","EncryptionKeyCreated","EncryptionKeyRotated","EntityWithTooManyOpenHandles","EtcHostsFileError","ExcessiveSMBAccessAttempt","ExternalTargetNotReachable","ExternallyTriggeredBackupError","ExternallyTriggeredRestoreError","FailedFailbackOpAlert","FailedFailoverOpAlert","FailedPrepareFailbackOpAlert","FailedTeardownOpAlert","FailedTestAndDevOpAlert","FailedToChangeAuthForBackupView","FanInserted","FanRemoved","FanSpeedOutOfLowRange","FirewallError","FirewalldServiceStartedAlert","FirewalldServiceStoppedAlert","FirmwareIncompatible","ForcefulRemoveNodeWarning","FragmentActionsRepeatedlyFailingAlert","FrequentProcessRestarts","GCStalledAlert","GatewayUnexpected","GlobalProtectionPolicyUpdateRejected","HeavyFileOperationContention","HighClusterUtilization","HighNonDedupToDedupPercent","HighRPCLatencies","HighUniqueUntrackedYodaPhysicalUsageAlert","HighUnreachableChunksAlert","HighUnreclaimedGarbageAlert","HostShellAccessExpiry","IceboxDedupCacheFull","ImbalanceThresholdExceededAlert","ImportantAwarenessCommunication","InactivityUITimeoutChanged","InconsistentInterfaceGroupSpeed","InconsistentStaticRoutes","IndexingBacklog","IndexingItemSkippedAlert","IndexingPaused","InsecureClientDetected","InsufficientResourcesToLaunchSysSrvPod","InternalSchedulingWarning","InvalidAppsSubnet","InvalidLicense","InvalidState","IpMigrationOnBondFailed","IpmiConfigAbsent","IpmiEvent","IpmiNetworkConfigFailed","IpmiSelCleared","IpmiUnreachable","IpmiUserUpdateFailed","IsilonChangelistCleanupFailed","KMSCertificateExpiration","KMSCertificateWillExpire","KMSError","KMSFailover","KMSImportExportError","KMSUnreachable","KernelPanic","KeyObjectCreated","KeyObjectDestroyed","KeyRotationPolicyChanged","KeystoneNotReachable","KnownIssueDetectedAlert","KnownIssueDetectedCommand","KnownIssueDetectedDoc","KnownIssueDetectedGflag","KnownIssueDetectedHotfix","KnownIssueDetectedPatch","KubernetesControlPlaneNotUp","KubernetesControlPlaneUp","KubernetesObjectsCleanupAlert","KubernetesSourceCleanupFailure","KubernetesSourceDeploymentFailure","KubernetesUnquiesceFailure","LambdaValidationFailed","LessCPUCore","LicenseAboutToExpire","LicenseAccountOverUse","LicenseExpired","LicenseIdentityInvalid","LicenseServerUnreachable","LicenseStatsHistoryCollection","LinkIsDown","LinkIsUp","LinkStatsIsNotNormal","LogicalVolumeNamingFallbackAlert","LowFaultTolerantStorageDomain","LowReplicationFactor","MagnetoAPIUnhealthy","MagnetoHighMemoryUsageDuringRecovery","MagnetoMasterHighMemoryUsage","MagnetoStateDBWriteFailure","MagnetoUnableToReachYoda","ManualBackgroundSystemThrottlingApplied","MarkDiskForRemoval","MediaErrorDuringArchival","MediaErrorDuringRestore","MemCorrectableEcc","MemUncorrectableEcc","MetadataCanRunOutOfSpaceUponFailure","MetadataCannotAchieveConfiguredFaultToleranceFactor","MetadataCannotTolerateAnymoreFailures","MetadataDiskRanOutOfSpace","MetadataInconsistencyAlert","MetadataInstanceHasUnrecoverableError","MetadataMigrationUsingSlowerDataTransferMode","MetadataMigrationsNotProgressing","MetadataMovedToFlashblade","MetadataServerUnreachable","MetadataShuffleNotProgressing","MetadataSizeExceedsThreshold","MetadataUnavailable","MicrosoftGraphAccessTokenFetchFailed","MicrosoftGraphClientSecretExpiry","MicrosoftSmtpDeprecated","MissedBackupRuns","MissingDisk","MissingDiskFiles","MissingVMBackup","MorphedGarbageThresholdExceededAlert","MtuUnexpected","NASVaultIsFull","NasSourceSnapshotDeletionFailed","NetBackupMediaServerUnhealthy","NetworkInterfaceFlaky","NetworkManagerMigrationFailure","NetworkRPCTimeoutRecovered","NetworkRPCTimeoutThresholdExceeded","NetworkStatsIsNotNormal","NewDiskFound","NewPatchAvailable","NewUpgradePackagesAvailable","NexusFaultIsolationRecovery","NfsShareNotHealthy","NisDomainNotReachable","NodeChassisChanged","NodeConnectivityFailed","NodeFailureIsNotTolerated","NodeInserted","NodeMarkedForRemoval","NodeNotPresentInKubernetesCluster","NodePingFailed","NodePoweredOff","NodePresentInKubernetesCluster","NodeRebooted","NodeRebootedForYodaStuck","NodeRemovalStuck","NodeRemoved","NodeTcpOpenConnectionsExceeded","NodeTcpOrphanConnectionsExceeded","NodeVirtualizationSupportDisabled","NonEmptyUnmountedDirectory","NotEnoughNodes","NtpServerUnReachable","ObjectBackupFailed","ObjectBackupSlaViolated","ObjectDeletionRejected","ObjectServiceClientTimeouts","ObjectServiceGlobalIngressPaused","ObjectServiceLocalIngressPaused","ObjectServiceObjectVersionsLimitReached","ObjectServiceServerTimeouts","ObjectServiceTooManyRequests","ObjectStorePortalInitializationFailure","OracleMountFailure","OracleRestoreChainBreak","OracleUnresponsiveProgressQuery","OrphanEntityValueVersionMismatch","OutOfComplianceBackupRuns","OutOfMemoryRestart","OverwriteThrottlingScheduleAlert","PolicyDatalockChanged","PolicyDatalockDurationChanged","PolicyFieldsDeprecated","PossibleMetadataInconsistency","PotentialClusterError","PotentialMinorClusterError","PowerSupplyAcLost","PowerSupplyAcRestored","PowerSupplyInserted","PowerSupplyRemoved","PrincipalWithNonViewerRole","ProactiveFullBackup","ProductModelIncompatible","ProductModelInterfacesInconsistency","ProgressMonitorFailure","ProtectedObjectCancelledBlackoutWindow","ProtectedObjectFailed","ProtectedObjectSlaViolated","ProtectionGroupArchivalBacklog","ProtectionGroupCancelledBlackoutWindow","ProtectionGroupDeleted","ProtectionGroupModified","ProtectionGroupProgressingSlowly","ProtectionGroupReplicationBacklog","ProtectionGroupReplicationFailed","ProtectionGroupSlaViolated","ProtectionGroupStuckReplicationTask","ProtectionGroupSucceeded","ProtectionGroupWarning","ProtectionPolicyDeleted","ProtectionPolicyModified","ProtectionRunExpiring","ProtectionRunModified","ProtectionServiceNotInitialized","ProtectionTaskNotProgressing","ProxyServerUnreachable","RaidDegraded","RaidInactive","RecentLogBeingRotated","RemoteClusterNotReachable","RemoteIndexingFallback","RemoteReplicationBackupUserQuotaSkipped","RemoteReplicationEncryptionKeyMismatch","RemoteReplicationFileSkipped","RemoteReplicationRestoreUserQuotaSkipped","RemoteReplicationSetupIncompatible","RemoteReplicationTaskFailed","RemoteReplicationTaskStuck","RemoteReplicationTrackingViewUpdateFailed","RemoteStorageCapacityChanged","RemoteStorageConfigureFailed","RemoteStorageDataIpUnreachable","RemoteStorageFileSystemDeleted","RemoteStorageFileSystemMountFailed","RemoteStorageFileSystemUsageHigh","RemoteStorageManagementIpUnreachable","RemoteStorageRegistrationInvalid","RemoteStorageUnexpectedNfsExportRules","RemoteStorageUsageHigh","RemoveNodeSuccess","RepeatedlyFailingShardAlert","ReplicationHandshakeStuck","RestoreJobFailed","RestoreJobStuck","RestoreSnapshotFailed","RestoreSnapshotStarted","RestoreSnapshotSucceeded","RestoreTaskFailed","RestoreTaskWarning","RhinoUnhealthy","RootPartitionSpaceCheckFailed","RoutesMigrationOnBondFailed","RoutingDaemonDown","RpmPackageVersionMismatched","SSHLoginFailure","SSHLoginSuccess","ScribeBackgroundOpsStalling","ScriptRunError","SearchClusterHealth","SearchIndexManualMigrationNeeded","SearchIndexMigrationBacklog","SearchIndexMigrationFinished","SearchIndexMigrationTriggered","SearchIndexShuffleNotProgressing","SearchIndexSizeExceedsThreshold","SearchIndexUnavailable","SearchNodeBusy","SecureShellDisabled","SecureShellEnabled","SecurityPolicyDenial","ServiceDown","ServiceGflagsChanged","ServiceVersionsMismatched","SilicomNicFound","SmallMemorySize","SourceConnectivityFailure","SourceRegistrationFailure","SsdMediaError","SshKeyMismatch","SshTimeoutChanged","StaleDirsFoundInYodaCloneBackupViews","StorageDomainQuota","StorageDomainSpaceUsageHigh","SuccessfulFailbackOpAlert","SuccessfulFailoverOpAlert","SuccessfulPrepareFailbackOpAlert","SuccessfulTeardownOpAlert","SuccessfulTestAndDevOpAlert","SupportChannelAboutToClose","SupportChannelExtension","SwitchCongestion","SwitchLegacyGlacierToGlacierTier","SwitchedToSpaceMode","SysSrvcErrors","SystemLedAmber","SystemServiceAppInstallationFailed","SystemServiceAppInstallationSuccess","TablesLargerThanExpected","TaskProgressHung","TeamsPublicChannelsIndexingAlert","TempOutOfHighRange","TempOutOfLowRange","TenantCertReachingExpiry","TenantCertRenewed","TenantIndexingConfigMissing","ThermalTripTriggered","TimeConsumingShardAlert","TimeService","UILoginFailure","UILoginSuccess","UIUserLockout","UnexpectedInterfaceIpSetting","UnexpectedIpAddress","UnlicensedCluster","UnregisterExternalTargetFailed","UnregisteredCluster","UnresponsiveSubProcessFailure","UnusedGflags","UpgradeCancelled","UpgradeExternalTarget","UpgradeFailed","UpgradeStarted","UpgradeStuck","UpgradeSucceeded","UsbDiskFound","UserAccountIsAboutToBeLocked","UserDefaultPassword","UserExceededQuotaAlertLimit","UserTuningsStuckAlertId","UsersExceededQuota","VLANUnexpected","VMCrackingSkipped","VMMigrationIdentified","VMOptimizedNTFSVolumeIndexingSkipped","VMOptimizedXFSVolumeIndexingSkipped","VMVolumeIndexingSkipped","VMVolumesNotDiscovered","VMWareMountFailure","ValidAppsSubnet","VaultConfigValidationFailed","VaultWindowIncompleteReplications","VerifyNonExistentBrickFailed","VerifyRemoteClusterConnection","VerifyVlanHostName","ViewCloneMetadataBloat","ViewFailoverDuplicateViewUID","ViewFailoverFailed","ViewFailoverReplicationFailed","ViewFailoverStateUpdateFailed","ViewFailoverStuck","ViewLatencyHigh","ViewQuota","ViewSlowProtocolOp","VipPingFailed","VirtualApplianceResourcesUnexpected","VoltOutOfHighRange","VoltOutOfLowRange","WatchdogTriggered","WormChangeForGroupAlert","WormChangeForPolicyAlert","WriteLimit","YodaAgentUnhealthy","YodaNotifyError","kBrickMetadataInconsistentState","kIntegralVolumeReachingMaxCapacity"]

### command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-c', '--clustername', nargs='+', type=str, default=None)
parser.add_argument('-cl', '--clusters', type=str, default=None)
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-pwd', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-add', '--add', type=str, action='append', default=None)
parser.add_argument('-remove', '--remove', type=str, action='append', default=None)
parser.add_argument('-rulename', '--rulename', type=str, action='append', default=None)
parser.add_argument('-updatename', '--updatename', type=str, default=None)
parser.add_argument('-updatetypes', '--updatetypes', action='store_true')
parser.add_argument('-debug', '--debug', action='store_true')

args = parser.parse_args()

vip = args.vip
username = args.username
domain = args.domain
clustername = args.clustername
clusterlist = args.clusters
mcm = args.mcm
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
mfacode = args.mfacode
emailmfacode = args.emailmfacode
addEmails = args.add or []
removeEmails = args.remove or []
ruleNames = args.rulename or []
updatename = args.updatename
updatetypes = args.updatetypes
debug = args.debug

if updatename is not None and len(ruleNames) != 1:
    print('-updatename requires exactly one -rulename to be specified')
    exit()

# gather server list
def gatherList(param=None, filename=None, name='items', required=True):
    items = []
    if param is not None:
        for item in param:
            items.append(item)
    if filename is not None:
        f = open(filename, 'r')
        items += [s.strip() for s in f.readlines() if s.strip() != '']
        f.close()
    if required is True and len(items) == 0:
        print('no %s specified' % name)
        exit()
    return items

# get list of clusters
clusternames = gatherList(clustername, clusterlist, name='clusters', required=True)

#Date
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")

if debug:
    enableCohesityAPIDebugger()

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)


# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================



for clustername in clusternames:
    heliosCluster(clustername)
    print(clustername)

    if LAST_API_ERROR() != 'OK':
        continue

    matchingHeliosClusters = [c for c in heliosClusters() if c['name'].lower() == clustername.lower()]
    if len(matchingHeliosClusters) > 0:
        COHESITY_API['HEADER']['clusterid'] = str(matchingHeliosClusters[0]['clusterId'])
        COHESITY_API['HEADER']['x-cohesity-service-context'] = 'Mcm'
    else:
        COHESITY_API['HEADER'].pop('clusterid', None)
        COHESITY_API['HEADER'].pop('x-cohesity-service-context', None)

    #Code starts here
    rules = api('get', 'alertNotificationRules') or []

    for rule in rules:
        ruleName = rule.get('ruleName', '')

        if len(ruleNames) > 0 and ruleName not in ruleNames:
            continue

        ruleId = rule.get('ruleId')
        changed = False

        if updatename is not None and updatename != ruleName:
            rule['ruleName'] = updatename
            changed = True

        if updatetypes and (rule.get('alertTypeList') != ALL_ALERT_TYPE_IDS or rule.get('alertNames') != ALL_ALERT_NAMES):
            rule['alertTypeList'] = ALL_ALERT_TYPE_IDS
            rule['alertNames'] = ALL_ALERT_NAMES
            changed = True

        if len(addEmails) > 0 or len(removeEmails) > 0:
            targets = rule.get('emailDeliveryTargets', []) or []

            if len(removeEmails) > 0:
                keptTargets = [t for t in targets if t.get('emailAddress') not in removeEmails]
                if len(keptTargets) != len(targets):
                    changed = True
                targets = keptTargets

            if len(addEmails) > 0:
                existingEmails = [t.get('emailAddress') for t in targets]
                newTargets = [
                    {
                        "emailAddress": e,
                        "locale": "en-us",
                        "recipientType": "kTo"
                    }
                    for e in addEmails
                    if e not in existingEmails
                ]
                if len(newTargets) > 0:
                    changed = True
                targets = targets + newTargets

            rule['emailDeliveryTargets'] = targets

        if changed:
            print('  updating rule %s %s' % (ruleName, ruleId))
            body = dict(rule)
            if 'webHookDeliveryTargets' not in body:
                body['webHookDeliveryTargets'] = body.pop('webhookDeliveryTargets', [])
            result = api('put', 'alertNotificationRules', body)
            if LAST_API_ERROR() != 'OK':
                print('  *** failed to update rule %s: %s' % (ruleName, LAST_API_ERROR()))
                print('  raw rule object for troubleshooting:')
                print(json.dumps(body, indent=2))
