import {Provider} from 'react-redux';
import AppContent from "./AppContent.tsx";
import {store} from "./store";

function App() {
    return (
        <Provider store={store}>
            <AppContent />
        </Provider>
    );
}

export default App;
