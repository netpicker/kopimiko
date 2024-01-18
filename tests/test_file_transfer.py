
import pytest

from kopimiko import FileTransferError, FileTransferInfo


@pytest.mark.parametrize('fti, expected', [
    (dict(), ''),
    (dict(password='pass'), ''),
    (dict(username='user', password=None), 'user@'),
    (dict(username='user', password=''), 'user:@'),
    (dict(username='user', password='pass'), 'user:pass@'),
])
def test_fti_credentials(fti, expected):
    assert FileTransferInfo(**fti).credentials == expected


def test_fti(tmp_path_factory):
    vol = tmp_path_factory.mktemp("data")
    fti = FileTransferInfo(
        dst_volume=str(vol),
        dst_file='data.cfg'
    )
    with pytest.raises(FileTransferError):
        fti.check_destination()
    with open(fti.destination_filename, 'w') as f:
        with pytest.raises(FileTransferError):
            fti.check_destination()
        f.write('foo')
    assert fti.check_destination() == fti.destination_filename
