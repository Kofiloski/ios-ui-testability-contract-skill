import SwiftUI

struct RecipeFormView: View {
    @State private var url = ""

    var body: some View {
        VStack {
            Text("Add Recipe")
            TextField("Video URL", text: $url)
                .textFieldStyle(.roundedBorder)
        }
        .accessibilityIdentifier("sample.recipeForm")
    }
}
