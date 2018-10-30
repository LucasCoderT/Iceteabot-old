from discord.ext.commands.errors import CommandError, UserInputError, BadArgument


class NotGuildOwner(CommandError):
    pass


class NotDirectMessage(CommandError):
    pass


class NotAdministrator(CommandError):
    pass


class MissingPermissions(CommandError):
    pass


class WrongChannel(CommandError):
    pass


class NotModerator(CommandError):
    pass


class EkGameNotOpen(CommandError):
    pass


class EKGameNotCreated(CommandError):
    pass


class EkGameAlreadyExists(CommandError):
    pass


class TagNotFound(CommandError):
    def __init__(self, param):
        self.param = param
        super().__init__()


class TagAlreadyExists(CommandError):
    def __init__(self, param):
        self.param = param
        super().__init__('{0} tag Already exists'.format(param))


class FeedNotFound(CommandError):
    pass


class FeedAlreadyExists(CommandError):
    pass


class InvalidRole(CommandError):
    pass


class BlackListed(CommandError):
    pass


class BadTask(UserInputError):
    pass


class NotRootCommand(UserInputError):
    def __init__(self, argument):
        super().__init__()
        self.command = argument


class MissingConnection(UserInputError):
    def __init__(self, connection, author):
        super().__init__(f"{author} has not connected an account for {connection}")
        self.connection = connection
        self.author = author


class NoAccountFound(BadArgument):
    def __index__(self):
        super().__init__(message=f"Unable to find an account with those credentials")
