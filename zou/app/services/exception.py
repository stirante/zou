from werkzeug.exceptions import NotFound, Forbidden, BadRequest, Unauthorized


class EpisodeNotFoundException(NotFound):
    pass


class SequenceNotFoundException(NotFound):
    pass


class ShotNotFoundException(NotFound):
    pass


class ConceptNotFoundException(NotFound):
    pass


class SceneNotFoundException(NotFound):
    pass


class AssetNotFoundException(NotFound):
    pass


class AssetInstanceNotFoundException(NotFound):
    pass


class AssetTypeNotFoundException(NotFound):
    pass


class AttachmentFileNotFoundException(NotFound):
    pass


class TaskNotFoundException(NotFound):
    pass


class PreviewBackgroundFileNotFoundException(NotFound):
    pass


class DepartmentNotFoundException(NotFound):
    pass


class StudioNotFoundException(NotFound):
    pass


class TaskStatusNotFoundException(NotFound):
    pass


class TaskTypeNotFoundException(NotFound):
    pass


class PersonInProtectedAccounts(Forbidden):
    pass


class PersonNotFoundException(NotFound):
    pass


class TimeSpentNotFoundException(NotFound):
    pass


class TimerNotFoundException(NotFound):
    pass


class ProjectNotFoundException(NotFound):
    pass


class WorkingFileNotFoundException(NotFound):
    pass


class OutputFileNotFoundException(NotFound):
    pass


class SoftwareNotFoundException(NotFound):
    pass


class OutputTypeNotFoundException(NotFound):
    pass


class PreviewFileNotFoundException(NotFound):
    pass


class PreviewFileReuploadNotAllowedException(BadRequest):
    pass


class CommentNotFoundException(NotFound):
    pass


class NewsNotFoundException(NotFound):
    pass


class EntityNotFoundException(NotFound):
    pass


class EntityLinkNotFoundException(NotFound):
    pass


class EntityTypeNotFoundException(NotFound):
    pass


class BuildJobNotFoundException(NotFound):
    pass


class PlaylistNotFoundException(NotFound):
    pass


class SearchFilterNotFoundException(NotFound):
    pass


class SearchFilterGroupNotFoundException(NotFound):
    pass


class NotificationNotFoundException(NotFound):
    pass


class SubscriptionNotFoundException(NotFound):
    pass


class MetadataDescriptorNotFoundException(NotFound):
    pass


class BudgetNotFoundException(NotFound):
    pass


class BudgetEntryNotFoundException(NotFound):
    pass


class MalformedFileTreeException(Exception):
    pass


class WrongFileTreeFileException(Exception):
    pass


class WrongPathFormatException(Exception):
    pass


class NoOutputFileException(Exception):
    pass


class NoAuthStrategyConfigured(Exception):
    pass


class WrongUserException(Exception):
    pass


class WrongPasswordException(Exception):
    pass


class MissingOTPException(Exception):
    def __init__(
        self,
        preferred_two_factor_authentication,
        two_factor_authentication_enabled,
    ):
        self.preferred_two_factor_authentication = (
            preferred_two_factor_authentication
        )
        self.two_factor_authentication_enabled = (
            two_factor_authentication_enabled
        )


class WrongOTPException(Exception):
    pass


class TOTPAlreadyEnabledException(Exception):
    pass


class TOTPNotEnabledException(Exception):
    pass


class TwoFactorAuthenticationNotEnabledException(Exception):
    pass


class FIDONoPreregistrationException(Exception):
    pass


class FIDOServerException(Exception):
    pass


class FIDONotEnabledException(Exception):
    pass


class EmailOTPAlreadyEnabledException(Exception):
    pass


class EmailOTPNotEnabledException(Exception):
    pass


class NoTwoFactorAuthenticationEnabled(Exception):
    pass


class TooMuchLoginFailedAttemps(Exception):
    pass


class UserCantConnectDueToNoFallback(Exception):
    pass


class UnactiveUserException(Unauthorized):
    pass


class WrongDateFormatException(Exception):
    pass


class EntryAlreadyExistsException(Exception):
    pass


class WrongParameterException(Exception):
    def __init__(self, message, dict=None):
        super().__init__(message)
        self.dict = dict


class WrongIdFormatException(Exception):
    pass


class ModelWithRelationsDeletionException(Exception):
    pass


class EditNotFoundException(NotFound):
    pass


class StatusAutomationNotFoundException(NotFound):
    pass


class WrongTaskTypeForEntityException(Exception):
    pass


class IsUserLimitReachedException(Exception):
    pass
