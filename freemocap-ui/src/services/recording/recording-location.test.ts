import assert from 'node:assert/strict';
import {test} from 'node:test';
import {recordingLocationFromPath, recordingLocationKey, recordingQuery} from './recording-location';
import {serverUrls} from '../../constants/server-urls';

test('same folder name in different roots has distinct cache identity', () => {
    assert.notEqual(recordingLocationKey('walking', 'C:\\one'), recordingLocationKey('walking', 'C:\\two'));
    assert.equal(recordingLocationKey('walking', ''), recordingLocationKey('walking', null));
    assert.equal(recordingLocationKey('walking'), recordingLocationKey('walking', null));
});

test('server paths and query parameters survive Windows, POSIX, roots and special characters', () => {
    for (const [path, parent, id] of [
        ['C:\\recordings\\walk #1', 'C:\\recordings', 'walk #1'],
        ['C:\\walk', 'C:\\', 'walk'], ['/walk', '/', 'walk'],
        ['/recordings/walk/', '/recordings', 'walk'],
        ['\\\\server\\share\\walk', '\\\\server\\share', 'walk'],
    ]) {
        const location = recordingLocationFromPath(path);
        assert.deepEqual(location, {recordingId: id, recordingParentDirectory: parent});
        assert.equal(new URLSearchParams(recordingQuery(parent)).get('recording_parent_directory'), parent);
    }
    assert.throws(() => recordingLocationFromPath('walking'));
    assert.throws(() => recordingLocationFromPath('/recordings/..'));
});

test('resource URLs encode identity once and preserve parent and revision', () => {
    const url = new URL(serverUrls.recordingResource('walk #1', '/parquet', 'C:\\recordings & clips', {revision: 'rev+2'}));
    assert.equal(url.pathname, '/freemocap/recordings/walk%20%231/parquet');
    assert.equal(url.searchParams.get('recording_parent_directory'), 'C:\\recordings & clips');
    assert.equal(url.searchParams.get('revision'), 'rev+2');
    assert.equal(new URL(serverUrls.endpoints.playbackBundle('walk')).pathname, '/freemocap/recordings/walk/playback/bundle');
    assert.equal(new URL(serverUrls.endpoints.playbackVideoStream('walk', 'camera #1.mp4')).pathname, '/freemocap/recordings/walk/videos/camera%20%231.mp4');
});
