async def entry_to_code(ctx, entries):
    width = max(map(lambda t: len(t[0]), entries))
    output = ['```']
    fmt = '{0:<{width}}: {1}'
    for name, entry in entries:
        output.append(fmt.format(name, entry, width=width))
    output.append('```')
    await ctx.send('\n'.join(output))

async def indented_entry_to_code(ctx, entries):
    width = max(map(lambda t: len(t[0]), entries))
    output = ['```']
    fmt = '\u200b{0:>{width}}: {1}'
    for name, entry in entries:
        output.append(fmt.format(name, entry, width=width))
    output.append('```')
    await ctx.send('\n'.join(output))

async def too_many_matches(ctx, msg, matches, entry):
    check = lambda m: m.content.isdigit()
    await ctx.send('There are too many matches... Which one did you mean? **Only say the number**.')
    await ctx.send('\n'.join(map(entry, enumerate(matches, 1))))

    # only give them 3 tries.
    for i in range(3):
        message = await ctx.wait_for_message(author=msg.author, channel=msg.channel, check=check)
        index = int(message.content)
        try:
            return matches[index - 1]
        except:
            await ctx.send('Please give me a valid number. {} tries remaining...'.format(2 - i))

    raise ValueError('Too many tries. Goodbye.')