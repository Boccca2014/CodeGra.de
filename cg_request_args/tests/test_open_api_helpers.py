from cg_request_args.open_api import _doc_without_sphinx


def test_doc_without_sphinx():
    def a():
        """This is a comment.

        .. :quickref: Ignored; Haha ignored

        More comments.

        .. warning:: A warning

        .. note::

            A note

        :param a: Wow ignore this. Wow ignore this. Wow ignore this. Wow ignore
                  this. Wow ignore this. Wow ignore this. Wow ignore this.
        :returns: Nothing.

        But included.
        """

    assert _doc_without_sphinx(a.__doc__).split('\n') == [
        'This is a comment.',
        '',
        '',
        'More comments.',
        '',
        'A warning',
        '',
        '',
        'A note',
        '',
        '',
        'But included.',
    ]
